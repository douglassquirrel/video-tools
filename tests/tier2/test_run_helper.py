"""The tests' own helper, conftest.run: it calls a command's main inside the test, in the test's own process (so
coverage measures it with no program started), with the test's settings and an empty working folder, and puts the
process back as it found it afterwards. conftest.run_program starts the file as a program, as a user runs it."""

import os
import subprocess
import sys

import pytest

from tests.tier2.conftest import REPO, STUBS, run, run_program


@pytest.fixture
def started(monkeypatch):
    """The argument lists of every program started while the test runs, passed on to the real Popen."""
    calls = []
    real = subprocess.Popen

    def recording(args, *rest, **kwargs):
        calls.append([str(a) for a in args])
        return real(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording)
    return calls


def commands_started(calls, command):
    return [c for c in calls if os.path.join(REPO, command) in c]


@pytest.mark.parametrize("command", ["compare-video"])
def test_run_calls_the_command_inside_the_test_and_starts_no_program_for_it(started, command):
    code, out, err = run(command, "--help")
    assert (code, err) == (0, "") and out.startswith(f"usage: {command}")
    assert commands_started(started, command) == []


@pytest.mark.parametrize("command", ["compare-video"])
def test_run_program_starts_the_file_as_a_program(started, command):
    code, out, err = run_program(command, "--help")
    assert (code, err) == (0, "") and out.startswith(f"usage: {command}")
    assert len(commands_started(started, command)) == 1


@pytest.mark.parametrize("command", ["compare-video"])
def test_run_reports_an_argparse_refusal_as_exit_2_with_the_usage_on_stderr(command):
    code, out, err = run(command)
    assert code == 2 and out == "" and err.startswith(f"usage: {command}")


def test_run_puts_back_the_environment_the_working_folder_the_import_path_and_the_modules(tmp_path, monkeypatch):
    from videotools import compare_video
    imported = []

    def main(argv):     # as narrate does: imports the speech model, here the stand-in that PYTHONPATH names
        import kokoro_onnx
        imported.append(kokoro_onnx.__file__)
        return 0

    monkeypatch.setattr(compare_video, "main", main)
    for name in [m for m in sys.modules if m.startswith("kokoro_onnx")]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.delenv("VIDEO_TOOLS_CONF", raising=False)
    environ, folder, path = dict(os.environ), os.getcwd(), list(sys.path)
    modules = set(sys.modules)
    result = run("compare-video", env={"VIDEO_TOOLS_CONF": str(tmp_path / "v.conf"), "PYTHONPATH": STUBS})
    assert result == (0, "", "") and imported == [os.path.join(STUBS, "kokoro_onnx", "__init__.py")]
    assert (dict(os.environ), os.getcwd(), list(sys.path)) == (environ, folder, path)
    assert [m for m in set(sys.modules) - modules if m.startswith("kokoro_onnx")] == []


def test_run_gives_the_command_the_tests_settings_and_an_empty_working_folder(tmp_path, monkeypatch):
    seen = {}
    from videotools import compare_video

    def main(argv):
        seen.update(conf=os.environ.get("VIDEO_TOOLS_CONF"), folder=os.listdir("."), argv=argv,
                    stand_in=os.environ.get("VIDEO_TOOLS_STUBS"), user_python=os.environ.get("VIDEO_TOOLS_PYTHON"))
        print("out")
        sys.stderr.write("err\n")
        return 3

    monkeypatch.setattr(compare_video, "main", main)
    monkeypatch.setenv("VIDEO_TOOLS_PYTHON", "/the/users/own/python")
    assert run("compare-video", "a b.mp4", 5, env={"VIDEO_TOOLS_CONF": "x.conf"}) == (3, "out\n", "err\n")
    assert seen == {"conf": "x.conf", "folder": [], "argv": ["a b.mp4", "5"], "stand_in": STUBS, "user_python": None}
