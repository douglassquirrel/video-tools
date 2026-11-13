"""A package a command needs but this Python lacks is one line naming it and the install, exit 4
(taken in from training-video-tools at fc6091a)."""

import os
import sys

import pytest

from tests.tier2.conftest import fake_media, run

HINT = ('; from the Linux device shell, set VIDEO_TOOLS_PYTHON to a Python that has it '
        '(README, "Running from the Linux device shell")')


def hidden(tmp_path, module):
    """A folder for PYTHONPATH where `module` raises ImportError, shadowing the real one."""
    folder = tmp_path / "hidden"
    folder.mkdir(exist_ok=True)
    (folder / f"{module}.py").write_text(f"raise ImportError(\"No module named '{module}'\")\n")
    return {"PYTHONPATH": str(folder), "VIDEO_TOOLS_PYTHON": None}


def message(prog, pip):
    return (f"{prog}: the Python package '{pip}' is not installed in this Python ({sys.executable}); "
            f"install it with .venv/bin/pip install {pip}")


@pytest.fixture
def video(tmp_path):
    return fake_media(str(tmp_path / "in" / "video.mp4"), duration="8.0", frames="240", colours="0:1.2.3")


@pytest.mark.parametrize("command, args, module, pip", [
    ("stills", ["--at", "1", "--out", "stills-folder"], "PIL", "Pillow"),
    ("compare-video", ["SELF"], "numpy", "numpy"),                       # SELF: the video again
    ("compare-video", ["SELF", "--sheet", "sheet.png"], "PIL", "Pillow"),
])
def test_a_missing_package_is_named_with_its_install_line_exit_4(video, ffstub, tmp_path, command, args, module,
                                                                   pip):
    env = dict(ffstub, **hidden(tmp_path, module))
    args = [video if a == "SELF" else a for a in args]
    code, out, err = run(command, video, *args, env=env, cwd=tmp_path)
    assert (code, out) == (4, ""), err
    assert "Traceback" not in err
    assert err == message(command, pip) + HINT + "\n"
    assert not any(os.path.exists(tmp_path / f) for f in ("sheet.png", "stills-folder"))


def test_with_video_tools_python_set_the_device_shell_hint_is_left_out(video, ffstub, tmp_path):
    env = dict(ffstub, **hidden(tmp_path, "PIL"))
    env["VIDEO_TOOLS_PYTHON"] = sys.executable
    code, out, err = run("stills", video, "--at", "1", "--out", tmp_path / "stills", env=env)
    assert (code, out) == (4, "")
    assert err == message("stills", "Pillow") + "\n"
