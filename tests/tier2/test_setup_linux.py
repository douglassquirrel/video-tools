"""setup-linux: the device shell's venv, packages, model check, config and environment lines
(training-video-tools' item 27, taken in at fc6091a)."""

import json
import os
import sys

import pytest

from tests.tier2.conftest import REPO, STUBS, run

PACKAGES = ["numpy", "soundfile", "kokoro-onnx==0.6.1", "Pillow"]
IMPORTS = "import numpy, soundfile, kokoro_onnx, PIL"


@pytest.fixture
def pystub(tmp_path):
    """A stub python3 first on PATH (tests/stubs/pystub.py) that records every call; the environment to
    run with, plus `python3` (its path), `venv`, `model` (with both files) and `conf` (missing) paths."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    python3 = bin_dir / "python3"
    python3.write_text(f"#!/bin/sh\nunset COVERAGE_PROCESS_START\nPYSTUB_SELF='{python3}' exec '{sys.executable}' '{os.path.join(STUBS, 'pystub.py')}' \"$@\"\n")
    python3.chmod(0o755)
    model = tmp_path / "kokoro"
    model.mkdir()
    (model / "model.onnx").write_bytes(b"")
    (model / "voices.npz").write_bytes(b"")
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}", "PYSTUB_LOG": str(tmp_path / "python-calls.jsonl"),
            "python3": str(python3), "venv": str(tmp_path / "work" / "venv"), "model": str(model),
            "conf": str(tmp_path / "work" / "video-tools.conf")}


def setup(env, *extra, venv=None, model=None, conf=None):
    """Run setup-linux with the stub's venv, model and conf unless given otherwise."""
    run_env = {k: v for k, v in env.items() if k in ("PATH", "PYSTUB_LOG", "PYSTUB_FAIL")}
    return run("setup-linux", "--venv", venv or env["venv"], "--model", model or env["model"],
               "--conf", conf or env["conf"], *extra, env=run_env)


def calls(env):
    """The stub's recorded calls, each [python, arg, ...], in order."""
    path = env["PYSTUB_LOG"]
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [[json.loads(line)["python"]] + json.loads(line)["args"] for line in f]


def lines_for(env):
    return (f"export VIDEO_TOOLS_PYTHON={env['venv']}/bin/python\n"
            f"export VIDEO_TOOLS_CONF={env['conf']}\n"
            "export PYTHONDONTWRITEBYTECODE=1\n")


def test_help_and_usage():
    code, out, err = run("setup-linux", "--help")
    assert code == 0 and " ".join(out.split()).startswith(
        "usage: setup-linux [-h] --venv DIR --model DIR --conf FILE [--dry-run]")
    assert "venv" in out and "model.onnx" in out
    assert "for the video-tools commands" in " ".join(out.split())
    code, out, err = run("setup-linux")
    assert code == 2 and "usage: setup-linux" in err
    assert "the following arguments are required: --venv, --model, --conf" in err


def test_a_venv_inside_the_checkout_is_refused_in_words_before_anything_runs(tmp_path):
    for inside in (REPO, os.path.join(REPO, "linux-venv"), os.path.join(REPO, "work", "venv")):
        code, out, err = run("setup-linux", "--venv", inside, "--model", tmp_path / "kokoro", "--conf", tmp_path / "c.conf")
        assert (code, out) == (2, "")
        assert err == (f"setup-linux: --venv {inside} is inside this checkout ({REPO}); the Linux venv must be made "
                       "outside it, or it would shadow the Mac's .venv (README, \"Running from the Linux device shell\")\n")
    assert not os.path.exists(os.path.join(REPO, "linux-venv")) and not os.path.exists(tmp_path / "c.conf")


def test_makes_the_venv_installs_the_packages_and_prints_the_three_lines(pystub):
    code, out, err = setup(pystub)
    venv_python = f"{pystub['venv']}/bin/python"
    assert calls(pystub) == [
        [pystub["python3"], "-m", "venv", "--system-site-packages", pystub["venv"]],
        [venv_python, "-c", IMPORTS],
        [venv_python, "-m", "pip", "install"] + PACKAGES,
    ]
    assert (code, out) == (0, lines_for(pystub))
    assert err == (f"setup-linux: made the venv at {pystub['venv']}\n"
                   f"setup-linux: installed {' '.join(PACKAGES)} into {pystub['venv']}\n"
                   f"setup-linux: wrote {pystub['conf']}\n")
    assert os.path.isfile(venv_python)


def test_a_second_run_finds_the_venv_the_packages_and_the_config_and_runs_only_the_import_check(pystub):
    assert setup(pystub)[0] == 0
    first = calls(pystub)
    conf_before = (open(pystub["conf"]).read(), os.stat(pystub["conf"]).st_mtime_ns)
    code, out, err = setup(pystub)
    assert (code, out, err) == (0, lines_for(pystub), "")
    assert calls(pystub) == first + [[f"{pystub['venv']}/bin/python", "-c", IMPORTS]]
    assert (open(pystub["conf"]).read(), os.stat(pystub["conf"]).st_mtime_ns) == conf_before


def test_a_config_naming_another_model_is_rewritten_with_its_other_lines_kept(pystub):
    os.makedirs(os.path.dirname(pystub["conf"]))
    with open(pystub["conf"], "w") as f:
        f.write("# this machine\nVOICE=bm_george\nSPEECH_MODEL_DIR='/old/place'   # moved\n# the end\n")
    code, out, err = setup(pystub)
    assert (code, out) == (0, lines_for(pystub))
    assert err.endswith(f"setup-linux: wrote {pystub['conf']}\n")
    assert open(pystub["conf"]).read() == f"# this machine\nVOICE=bm_george\nSPEECH_MODEL_DIR={pystub['model']}\n# the end\n"


def test_a_config_without_the_setting_gains_it_at_the_end(pystub):
    os.makedirs(os.path.dirname(pystub["conf"]))
    with open(pystub["conf"], "w") as f:
        f.write("VOICE=bm_george")          # no final newline
    code, out, err = setup(pystub)
    assert (code, out) == (0, lines_for(pystub))
    assert open(pystub["conf"]).read() == f"VOICE=bm_george\nSPEECH_MODEL_DIR={pystub['model']}\n"


def test_the_config_folder_is_made_when_it_is_missing(pystub, tmp_path):
    conf = str(tmp_path / "elsewhere" / "deeper" / "video-tools.conf")
    code, out, err = setup(pystub, conf=conf)
    assert code == 0 and out.splitlines()[1] == f"export VIDEO_TOOLS_CONF={conf}"
    assert open(conf).read() == f"SPEECH_MODEL_DIR={pystub['model']}\n"


def test_a_config_that_cannot_be_read_is_refused_in_words_and_left_alone(pystub):
    os.makedirs(os.path.dirname(pystub["conf"]))
    with open(pystub["conf"], "w") as f:
        f.write("SPEECH_MODEL_DIR=/old\nnot a setting\n")
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert err.endswith(f"setup-linux: {pystub['conf']} cannot be used as it is; fix it or name another file with --conf:\n"
                        f"{pystub['conf']}: line 2: not KEY=value: not a setting\n")
    assert open(pystub["conf"]).read() == "SPEECH_MODEL_DIR=/old\nnot a setting\n"


README_POINTER = 'as the README\'s "One-time set-up of the speech model" says'


def test_a_model_folder_without_the_files_is_reported_file_by_file_after_the_venv_is_made_exit_3(pystub):
    os.remove(os.path.join(pystub["model"], "model.onnx"))
    os.remove(os.path.join(pystub["model"], "voices.npz"))
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert err == (f"setup-linux: made the venv at {pystub['venv']}\n"
                   f"setup-linux: installed {' '.join(PACKAGES)} into {pystub['venv']}\n"
                   f"setup-linux: wrote {pystub['conf']}\n"
                   f"setup-linux: the model folder {pystub['model']} has no model.onnx; download it {README_POINTER}\n"
                   f"setup-linux: the model folder {pystub['model']} has no voices.npz; make it from the voices {README_POINTER}\n")
    assert len(calls(pystub)) == 3 and os.path.isfile(f"{pystub['venv']}/bin/python")
    assert open(pystub["conf"]).read() == f"SPEECH_MODEL_DIR={pystub['model']}\n"


def test_one_missing_model_file_is_the_one_named(pystub):
    os.remove(os.path.join(pystub["model"], "voices.npz"))
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert err.splitlines()[-1] == f"setup-linux: the model folder {pystub['model']} has no voices.npz; make it from the voices {README_POINTER}"
    assert "model.onnx" not in err


def test_a_model_folder_that_does_not_exist_is_one_message(pystub, tmp_path):
    missing = str(tmp_path / "no" / "kokoro")
    code, out, err = setup(pystub, model=missing)
    assert (code, out) == (3, "")
    assert err.splitlines()[-1] == f"setup-linux: the model folder {missing} does not exist; download the model into it {README_POINTER}"
    assert err.count("setup-linux: the model folder") == 1


def test_dry_run_with_nothing_in_place_says_what_it_would_do_and_runs_makes_and_writes_nothing(pystub):
    code, out, err = setup(pystub, "--dry-run")
    assert (code, err) == (0, "")
    assert out == (f"Would make the venv at {pystub['venv']}\n"
                   f"Would install {' '.join(PACKAGES)} into {pystub['venv']}\n"
                   f"Would write {pystub['conf']} with SPEECH_MODEL_DIR={pystub['model']}\n" + lines_for(pystub))
    assert calls(pystub) == []
    assert not os.path.exists(pystub["venv"]) and not os.path.exists(pystub["conf"])


def test_dry_run_with_everything_in_place_runs_only_the_import_check_and_prints_the_lines(pystub):
    assert setup(pystub)[0] == 0
    first = calls(pystub)
    code, out, err = setup(pystub, "--dry-run")
    assert (code, out, err) == (0, lines_for(pystub), "")
    assert calls(pystub) == first + [[f"{pystub['venv']}/bin/python", "-c", IMPORTS]]


def test_dry_run_with_the_venv_but_not_the_packages_would_install_and_installs_nothing(pystub):
    assert setup(pystub)[0] == 0
    os.remove(os.path.join(pystub["venv"], "installed"))         # the stub's mark of an install
    first = calls(pystub)
    code, out, err = setup(pystub, "--dry-run")
    assert (code, err) == (0, "")
    assert out == f"Would install {' '.join(PACKAGES)} into {pystub['venv']}\n" + lines_for(pystub)
    assert calls(pystub) == first + [[f"{pystub['venv']}/bin/python", "-c", IMPORTS]]
    assert not os.path.exists(os.path.join(pystub["venv"], "installed"))


def test_dry_run_with_the_model_missing_reports_it_after_what_it_would_do_exit_3(pystub):
    os.remove(os.path.join(pystub["model"], "model.onnx"))
    code, out, err = setup(pystub, "--dry-run")
    assert code == 3
    assert out == (f"Would make the venv at {pystub['venv']}\n"
                   f"Would install {' '.join(PACKAGES)} into {pystub['venv']}\n"
                   f"Would write {pystub['conf']} with SPEECH_MODEL_DIR={pystub['model']}\n")
    assert err == f"setup-linux: the model folder {pystub['model']} has no model.onnx; download it {README_POINTER}\n"
    assert calls(pystub) == [] and not os.path.exists(pystub["venv"]) and not os.path.exists(pystub["conf"])


def test_a_failing_venv_is_reported_in_words_with_its_last_lines_exit_3_and_nothing_else_runs(pystub):
    pystub["PYSTUB_FAIL"] = "venv"
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert err == (f"setup-linux: python3 -m venv --system-site-packages {pystub['venv']} failed (exit 1); its last lines:\n"
                   f"  Error: Command '['{pystub['venv']}/bin/python', '-m', 'ensurepip']' returned non-zero exit status 1.\n"
                   "Fix that (the venv module and pip must work on this machine) and run again\n")
    assert len(calls(pystub)) == 1 and not os.path.exists(pystub["conf"])


def test_a_failing_pip_is_reported_in_words_with_its_last_lines_exit_3_and_the_venv_kept(pystub):
    pystub["PYSTUB_FAIL"] = "pip"
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    venv_python = f"{pystub['venv']}/bin/python"
    assert err == (f"setup-linux: made the venv at {pystub['venv']}\n"
                   f"setup-linux: {venv_python} -m pip install {' '.join(PACKAGES)} failed (exit 1); its last lines:\n"
                   "  ERROR: Could not find a version that satisfies the requirement numpy (from versions: none)\n"
                   "  ERROR: No matching distribution found for numpy\n"
                   "Fix that (the network, or a package's build needs) and run again; the venv is kept\n")
    assert len(calls(pystub)) == 3 and os.path.isfile(venv_python) and not os.path.exists(pystub["conf"])


def test_no_python3_on_path_is_reported_in_words_exit_3_and_nothing_runs(pystub, tmp_path):
    pystub["PATH"] = str(tmp_path / "empty-bin")
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert err == "setup-linux: no python3 on PATH to make the venv with; install Python 3 or put it on PATH\n"
    assert calls(pystub) == [] and not os.path.exists(pystub["venv"])


def test_with_python3_on_path_but_the_venv_in_place_no_python3_is_needed(pystub, tmp_path):
    assert setup(pystub)[0] == 0
    pystub["PATH"] = str(tmp_path / "empty-bin")
    code, out, err = setup(pystub)
    assert (code, out, err) == (0, lines_for(pystub), "")


def test_paths_with_spaces_and_non_ascii_are_quoted_for_the_shell(pystub, tmp_path):
    venv = str(tmp_path / "wörk space" / "venv")
    conf = str(tmp_path / "wörk space" / "vidéo tools.conf")
    code, out, err = setup(pystub, venv=venv, conf=conf)
    assert (code, err) == (0, f"setup-linux: made the venv at {venv}\nsetup-linux: installed {' '.join(PACKAGES)} into {venv}\nsetup-linux: wrote {conf}\n")
    assert out == (f"export VIDEO_TOOLS_PYTHON='{venv}/bin/python'\nexport VIDEO_TOOLS_CONF='{conf}'\n"
                   "export PYTHONDONTWRITEBYTECODE=1\n")
    assert os.path.isfile(os.path.join(venv, "bin", "python")) and open(conf).read() == f"SPEECH_MODEL_DIR={pystub['model']}\n"


def test_a_failing_step_shows_only_its_last_five_lines(pystub):
    pystub["PYSTUB_FAIL"] = "pip-noisy"
    code, out, err = setup(pystub)
    assert (code, out) == (3, "")
    assert "build step 3\n" not in err
    assert "".join(f"  build step {i}\n" for i in range(4, 9)) in err


def test_a_commented_out_model_line_is_kept_and_the_setting_added(pystub):
    os.makedirs(os.path.dirname(pystub["conf"]))
    with open(pystub["conf"], "w") as f:
        f.write("# SPEECH_MODEL_DIR=/old/place\nVOICE=bm_george\n")
    code, out, err = setup(pystub)
    assert (code, out) == (0, lines_for(pystub))
    assert open(pystub["conf"]).read() == (f"# SPEECH_MODEL_DIR=/old/place\nVOICE=bm_george\n"
                                           f"SPEECH_MODEL_DIR={pystub['model']}\n")


def test_relative_paths_are_made_absolute_in_the_lines_and_the_config(pystub, tmp_path):
    run_env = {k: v for k, v in pystub.items() if k in ("PATH", "PYSTUB_LOG")}
    code, out, err = run("setup-linux", "--venv", "work/venv", "--model", "kokoro", "--conf", "work/v.conf",
                         env=run_env, cwd=tmp_path)
    assert code == 0, err
    assert out == (f"export VIDEO_TOOLS_PYTHON={tmp_path / 'work' / 'venv' / 'bin' / 'python'}\n"
                   f"export VIDEO_TOOLS_CONF={tmp_path / 'work' / 'v.conf'}\n"
                   "export PYTHONDONTWRITEBYTECODE=1\n")
    assert (tmp_path / "work" / "v.conf").read_text() == f"SPEECH_MODEL_DIR={tmp_path / 'kokoro'}\n"
