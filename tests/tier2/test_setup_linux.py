"""setup-linux: a wrapper of lobster-tools' prepare-venv (lobster-tools' Request 01; PLAN.md Settled 13 and 14). It
keeps its own flags, runs prepare-venv with this checkout as --project and its arguments unchanged, and gives back
prepare-venv's exit code. prepare-venv itself (the venv, the packages, the config, the model check, the export lines)
is tested in lobster-tools; here it is tests/stubs/prepare_venv.py, linked in as `prepare-venv`."""

import json
import os
import sys

import pytest

from tests.tier2.conftest import REPO, STUBS, run, run_program

USAGE = "usage: setup-linux [-h] --venv DIR --model DIR --conf FILE [--dry-run]"


def lobster_tools(folder):
    """A pretend lobster-tools checkout in `folder`, holding the stand-in as prepare-venv."""
    folder.mkdir(parents=True, exist_ok=True)
    os.symlink(os.path.join(STUBS, "prepare_venv.py"), folder / "prepare-venv")
    return folder


@pytest.fixture
def lt(tmp_path):
    """The environment for a run: LOBSTER_TOOLS naming a pretend checkout, HOME a folder with no mnt/ in it, and
    the stand-in's log."""
    home = tmp_path / "home"
    home.mkdir()
    return {"LOBSTER_TOOLS": str(lobster_tools(tmp_path / "lobster-tools")), "HOME": str(home),
            "PREPARE_VENV_STUB_LOG": str(tmp_path / "prepare-venv-calls.jsonl")}


def calls(env):
    """The stand-in's recorded runs, in order: {python, args, cwd}."""
    path = env["PREPARE_VENV_STUB_LOG"]
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


ARGS = ["--venv", "/tmp/work/venv", "--model", "/models/kokoro", "--conf", "/tmp/work/video-tools.conf"]


def test_help_names_its_own_flags_and_runs_nothing(lt):
    code, out, err = run("setup-linux", "--help", env=lt)
    assert (code, err) == (0, "") and out.startswith(USAGE)
    assert "prepare-venv" in out and "--project" not in out
    assert calls(lt) == []


@pytest.mark.parametrize("args", [[], ARGS[:4], ARGS[2:], ARGS + ["--project", "/x"]])
def test_a_flag_missing_or_unknown_is_a_usage_error_exit_2_before_prepare_venv_runs(lt, args):
    code, out, err = run("setup-linux", *args, env=lt)
    assert (code, out) == (2, "") and err.startswith(USAGE)
    assert calls(lt) == []


@pytest.mark.parametrize("extra", [[], ["--dry-run"]])
def test_runs_prepare_venv_with_this_python_this_checkout_as_the_project_and_its_arguments(lt, tmp_path, extra):
    code, _out, _err = run("setup-linux", *ARGS, *extra, env=lt, cwd=tmp_path)
    assert code == 0
    assert calls(lt) == [{"python": sys.executable, "cwd": str(tmp_path),
                          "args": ["--project", REPO] + ARGS + extra}]


def test_paths_with_spaces_quotes_dollars_and_non_ascii_are_handed_over_as_they_are(lt, tmp_path):
    odd = ["--venv", "work/a venv's $HOME", "--model", "modèles/kokoro \"v1\"", "--conf", "c\\onf;rm -rf x.conf"]
    assert run("setup-linux", *odd, env=lt, cwd=tmp_path)[0] == 0
    assert calls(lt)[0]["args"] == ["--project", REPO] + odd


@pytest.mark.parametrize("exit_code", [2, 3, 4])
def test_prepare_venvs_exit_code_is_its_own(lt, exit_code):
    code, _out, _err = run("setup-linux", *ARGS, env=dict(lt, PREPARE_VENV_STUB_EXIT=str(exit_code)))
    assert code == exit_code and len(calls(lt)) == 1


def test_without_the_setting_it_runs_the_prepare_venv_in_mnt_lobster_tools_under_home(lt, tmp_path):
    lobster_tools(tmp_path / "home" / "mnt" / "lobster-tools")
    os.remove(os.path.join(lt["LOBSTER_TOOLS"], "prepare-venv"))     # so a run of it would not be recorded
    assert run("setup-linux", *ARGS, env=dict(lt, LOBSTER_TOOLS=None))[0] == 0
    assert [c["args"][:2] for c in calls(lt)] == [["--project", REPO]]


def test_the_setting_wins_over_mnt_lobster_tools(lt, tmp_path):
    mnt = tmp_path / "home" / "mnt" / "lobster-tools"
    mnt.mkdir(parents=True)
    (mnt / "prepare-venv").write_text("import sys; sys.exit(9)\n")
    assert run("setup-linux", *ARGS, env=lt)[0] == 0 and len(calls(lt)) == 1


def test_a_setting_naming_a_folder_without_prepare_venv_is_one_message_exit_4(lt, tmp_path):
    lobster_tools(tmp_path / "home" / "mnt" / "lobster-tools")     # not used: the setting is what was asked for
    empty = tmp_path / "not-lobster-tools"
    empty.mkdir()
    code, out, err = run("setup-linux", *ARGS, env=dict(lt, LOBSTER_TOOLS=str(empty)))
    assert (code, out) == (4, "")
    assert err == (f"setup-linux: lobster-tools' prepare-venv is not in {empty}, which LOBSTER_TOOLS names; set "
                   "LOBSTER_TOOLS to the lobster-tools checkout (README, \"Running from the Linux device shell\")\n")
    assert calls(lt) == []


def test_no_setting_and_nothing_in_mnt_is_one_message_naming_both_exit_4(lt, tmp_path):
    code, out, err = run("setup-linux", *ARGS, env=dict(lt, LOBSTER_TOOLS=None))
    assert (code, out) == (4, "")
    mnt = tmp_path / "home" / "mnt" / "lobster-tools"
    assert err == (f"setup-linux: lobster-tools' prepare-venv is not in {mnt}, and LOBSTER_TOOLS is not set; connect "
                   "lobster-tools there, or set LOBSTER_TOOLS to its checkout (README, \"Running from the Linux "
                   "device shell\")\n")
    assert calls(lt) == []


def test_run_as_a_program_prepare_venvs_output_and_exit_code_come_through(lt, tmp_path):
    code, out, err = run_program("setup-linux", *ARGS, env=dict(lt, PREPARE_VENV_STUB_EXIT="3"), cwd=tmp_path)
    assert (code, out, err) == (3, "export VIDEO_TOOLS_PYTHON=/stand-in/venv/bin/python\n",
                                "prepare-venv: the stand-in ran\n")
    assert calls(lt)[0]["args"] == ["--project", REPO] + ARGS
