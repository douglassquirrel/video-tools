"""Tier 2: the command against stubs of ffmpeg and ffprobe, in its own temporary folders."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STUB = os.path.join(REPO, "tests", "stubs", "ffstub.py")

TRANSCRIPT = (
    "1\n00:00:00,000 --> 00:00:04,000\nIs this thing on?\n\n"
    "2\n00:00:04,000 --> 00:00:09,500\nWelcome to the show.\n\n"
    "3\n00:00:09,500 --> 00:00:15,000\nToday, cutting video.\n\n"
    "4\n00:00:15,000 --> 00:00:21,000\nThat's all,\nthank you.\n\n"
    "5\n00:00:21,000 --> 00:00:25,000\nIs it off yet?\n\n"
)


class Stubs:
    """The stub programs' folder and log, and what they are told to do."""

    def __init__(self, folder):
        self.bin = folder / "bin"
        self.bin.mkdir()
        self.log = folder / "ff-calls.jsonl"
        self.env = {"PATH": str(self.bin), "FFSTUB_LOG": str(self.log)}
        for name in ("ffmpeg", "ffprobe"):
            self.add(name)

    def add(self, name):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\nFFSTUB_NAME={name} exec '{sys.executable}' '{STUB}' \"$@\"\n")
        path.chmod(0o755)

    def remove(self, name):
        (self.bin / name).unlink()

    def calls(self, name=None):
        if not self.log.exists():
            return []
        calls = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        return [c["args"] for c in calls if name is None or c["name"] == name]


@pytest.fixture
def stubs(tmp_path, monkeypatch):
    s = Stubs(tmp_path)
    for k, v in s.env.items():
        monkeypatch.setenv(k, v)
    for k in ("FFPROBE_OUTPUT", "FFPROBE_EXIT", "FFMPEG_EXIT"):
        monkeypatch.delenv(k, raising=False)
    return s


@pytest.fixture
def inputs(tmp_path):
    """A pretend video and its transcript, in a folder of their own."""
    folder = tmp_path / "in"
    folder.mkdir()
    video = folder / "talk.mov"
    video.write_bytes(b"not really a video")
    srt = folder / "talk.srt"
    srt.write_text(TRANSCRIPT, encoding="utf-8")
    return video, srt


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cut_video(*args):
    """main() in this process: (exit code, stdout, stderr) via capsys in the caller."""
    from videotools.cut_video import main
    return main([str(a) for a in args])


def run_script(*args, cwd=None, env=None):
    """The real cut-video script, as a user runs it: (exit code, stdout, stderr)."""
    p = subprocess.run([sys.executable, os.path.join(REPO, "cut-video")] + [str(a) for a in args],
                       capture_output=True, text=True, cwd=cwd or REPO, env=env, check=False)
    return p.returncode, p.stdout, p.stderr


# ---- narrate, stills and compare-video (taken in from training-video-tools at fc6091a): the
# commands run as subprocesses, against tests/stubs/fakemedia.py as ffmpeg and ffprobe and the
# fake speech model in tests/stubs/kokoro_onnx/.

STUBS = os.path.join(REPO, "tests", "stubs")

# Settings the user's shell may export (the README tells device-shell users to export
# VIDEO_TOOLS_PYTHON and VIDEO_TOOLS_CONF) that would change what a command under test does: a test
# sets them on purpose or not at all. training-video-tools' own are dropped too.
USER_SETTINGS = ("VIDEO_TOOLS_PYTHON", "VIDEO_TOOLS_CONF", "VIDEO_TOOLS_VENV",
                 "TRAINING_VIDEO_TOOLS_PYTHON", "TRAINING_VIDEO_TOOLS_CONF", "TRAINING_VIDEO_TOOLS_VENV")


def clean_env(**overrides):
    """A copy of the environment without the user's own video-tools settings, plus `overrides`."""
    env = {k: v for k, v in os.environ.items() if k not in USER_SETTINGS}
    env.update(overrides)
    return env


COVERING = "VIDEO_TOOLS_TESTS_MEASURE"   # set by pytest_configure when this run measures coverage; in the
                                        # environment, since the tests may import this file under another name


def pytest_configure(config):
    if config.getoption("cov_source", None) and not config.getoption("no_cov", False):
        os.environ[COVERING] = "1"
    else:
        os.environ.pop(COVERING, None)


def run(command, *args, cwd=None, env=None):
    """Run a top-level command script with this Python; (exit code, stdout, stderr). Without `cwd`, from
    a fresh empty folder, so a relative path never lands in the checkout, even when the code is wrong."""
    full_env = clean_env()
    full_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if os.environ.get(COVERING):    # let coverage.py measure the subprocess too (pyproject.toml: parallel = true)
        full_env.setdefault("COVERAGE_PROCESS_START", os.path.join(REPO, "pyproject.toml"))
        full_env.setdefault("COVERAGE_FILE", os.path.join(REPO, ".coverage"))   # not the empty folder it runs in
    full_env.update(env or {})
    full_env = {k: v for k, v in full_env.items() if v is not None}   # None in `env` unsets a variable
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run([sys.executable, os.path.join(REPO, command)] + [str(a) for a in args],
                           capture_output=True, text=True, cwd=cwd or empty, env=full_env, check=False)
    return p.returncode, p.stdout, p.stderr


@pytest.fixture
def ffstub(tmp_path):
    """Stub ffmpeg and ffprobe (fakemedia.py) first on PATH, logging every call. Returns the environment."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("ffmpeg", "ffprobe"):
        path = bin_dir / name
        # The stub is not code under test: started without coverage's hook, it starts in a tenth of the time.
        path.write_text(f"#!/bin/sh\nunset COVERAGE_PROCESS_START\nFFSTUB_NAME={name} exec '{sys.executable}' "
                        f"'{os.path.join(STUBS, 'fakemedia.py')}' \"$@\"\n")
        path.chmod(0o755)
    return {"PATH": f"{bin_dir}:{os.environ['PATH']}", "FFSTUB_LOG": str(tmp_path / "ff-calls.jsonl")}


def ff_calls(env):
    """The stub's recorded calls: [{'ffmpeg': [...]} or {'ffprobe': [...]}] in order."""
    path = env["FFSTUB_LOG"]
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def fake_media(path, **fields):
    """A fake media file the stub understands: key=value lines."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(f"{k}={v}\n" for k, v in fields.items())
    return path


@pytest.fixture
def speech(tmp_path):
    """A fake speech model: the stub kokoro_onnx on PYTHONPATH, an empty model folder, a config
    naming it, and a log of the stub's calls. Returns the environment to run with."""
    model = tmp_path / "models" / "kokoro"
    model.mkdir(parents=True)
    (model / "model.onnx").write_bytes(b"")
    (model / "voices.npz").write_bytes(b"")
    conf = tmp_path / "video-tools.conf"
    conf.write_text(f"SPEECH_MODEL_DIR={model}\nVOICE=bm_george\n")
    log = tmp_path / "kokoro-calls.jsonl"
    return {"PYTHONPATH": STUBS, "VIDEO_TOOLS_CONF": str(conf), "KOKORO_STUB_LOG": str(log),
            "SPEECH_MODEL_DIR_FOR_TESTS": str(model)}


def stub_calls(env):
    """The stub speech model's recorded calls, in order."""
    path = env["KOKORO_STUB_LOG"]
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]
