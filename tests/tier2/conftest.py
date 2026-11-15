"""Tier 2: the command against stubs of ffmpeg and ffprobe, in its own temporary folders."""

import contextlib
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

TRANSCRIPT = (
    "1\n00:00:00,000 --> 00:00:04,000\nIs this thing on?\n\n"
    "2\n00:00:04,000 --> 00:00:09,500\nWelcome to the show.\n\n"
    "3\n00:00:09,500 --> 00:00:15,000\nToday, cutting video.\n\n"
    "4\n00:00:15,000 --> 00:00:21,000\nThat's all,\nthank you.\n\n"
    "5\n00:00:21,000 --> 00:00:25,000\nIs it off yet?\n\n"
)


# The stand-in programs are files in tests/stubs/ (*.sh), never written by a test: each test links them into
# its own folder under the program's name, because macOS takes about a seventh of a second over the first run
# of a script file it has not seen and a few thousandths over a new link to one it has run. They find the
# Python to run and this folder from these two variables, which every run below passes on. A test that needs
# a different stand-in removes its link and writes its own file; the run checks at its end that no shared one
# was written over (pytest_sessionfinish).
STAND_IN_ENV = {"VIDEO_TOOLS_STUB_PYTHON": sys.executable,
                "VIDEO_TOOLS_STUBS": os.path.join(REPO, "tests", "stubs")}


def stand_in_digests(folder):
    """{name: SHA-256} of each shared stand-in (*.sh) in `folder`."""
    return {name: hashlib.sha256(open(os.path.join(folder, name), "rb").read()).hexdigest()
            for name in sorted(os.listdir(folder)) if name.endswith(".sh")}


def written_over(before, folder):
    """The names of the stand-ins in `before` that are now different or gone from `folder`, sorted."""
    now = stand_in_digests(folder)
    return sorted(name for name, digest in before.items() if now.get(name) != digest)


STAND_INS_AT_START = stand_in_digests(STAND_IN_ENV["VIDEO_TOOLS_STUBS"])


def pytest_sessionfinish(session):
    changed = written_over(STAND_INS_AT_START, STAND_IN_ENV["VIDEO_TOOLS_STUBS"])
    if changed:
        sys.stderr.write(f"\nA test wrote over or removed the shared stand-in(s) {', '.join(changed)} in tests/stubs/: "
                         "a test must remove its link and write its own file instead. Restore them with git.\n")
        session.exitstatus = 1


class Stubs:
    """The stub programs' folder and log, and what they are told to do."""

    def __init__(self, folder):
        self.bin = folder / "bin"
        self.bin.mkdir()
        self.log = folder / "ff-calls.jsonl"
        self.env = dict(STAND_IN_ENV, PATH=str(self.bin), FFSTUB_LOG=str(self.log))
        for name in ("ffmpeg", "ffprobe"):
            self.add(name)

    def add(self, name):
        os.symlink(os.path.join(STAND_IN_ENV["VIDEO_TOOLS_STUBS"], "ffstub.sh"), self.bin / name)

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


# ---- narrate, stills, compare-video and setup-linux (taken in from training-video-tools at fc6091a): `run`
# calls each one's main inside the test and `run_program` starts it as a program, against tests/stubs/fakemedia.py
# as ffmpeg and ffprobe, the fake speech model in tests/stubs/kokoro_onnx/ and, for setup-linux, tests/stubs/prepare_venv.py as
# lobster-tools' prepare-venv.

STUBS = os.path.join(REPO, "tests", "stubs")

# Settings the user's shell may export (the README tells device-shell users to export
# VIDEO_TOOLS_PYTHON and VIDEO_TOOLS_CONF) that would change what a command under test does: a test
# sets them on purpose or not at all. training-video-tools' own are dropped too.
USER_SETTINGS = ("VIDEO_TOOLS_PYTHON", "VIDEO_TOOLS_CONF", "VIDEO_TOOLS_VENV",
                 "TRAINING_VIDEO_TOOLS_PYTHON", "TRAINING_VIDEO_TOOLS_CONF", "TRAINING_VIDEO_TOOLS_VENV")


def clean_env(**overrides):
    """A copy of the environment without the user's own video-tools settings, plus `overrides`."""
    env = {k: v for k, v in os.environ.items() if k not in USER_SETTINGS}
    env.update(STAND_IN_ENV)
    env.update(overrides)
    return env


COVERING = "VIDEO_TOOLS_TESTS_MEASURE"   # set by pytest_configure when this run measures coverage; in the
                                        # environment, since the tests may import this file under another name


def pytest_configure(config):
    if config.getoption("cov_source", None) and not config.getoption("no_cov", False):
        os.environ[COVERING] = "1"
    else:
        os.environ.pop(COVERING, None)


def run_program(command, *args, cwd=None, env=None):
    """Start a top-level command script as a program, with this Python, as a user runs it; (exit code, stdout,
    stderr). For the few tests that must (the shared rules, "Tiers": most call `run` instead), since coverage's
    hook starting in each program costs a tenth of a second or more. Without `cwd`, from a fresh empty folder, so a
    relative path never lands in the checkout, even when the code is wrong."""
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


# The commands `run` calls inside the test, by the module whose main it calls. cut-video has its own helpers above.
MAINS = {"compare-video": "videotools.compare_video", "stills": "videotools.stills",
         "narrate": "videotools.narrate", "setup-linux": "videotools.setup_linux"}


def run(command, *args, cwd=None, env=None):
    """Call a command's main inside the test, in this process, so coverage measures it with no program started;
    (exit code, stdout, stderr), as run_program gives them. The environment is clean_env() with `env` over it
    (None unsets a variable), PYTHONPATH's folders go at the front of the import path, and the working folder is
    `cwd` or a fresh empty one; all of it, and any module imported from PYTHONPATH, is put back afterwards."""
    full_env = clean_env()
    full_env.update(env or {})
    full_env = {k: v for k, v in full_env.items() if v is not None}
    extra = [p for p in full_env.get("PYTHONPATH", "").split(os.pathsep) if p]
    environ, folder, path, modules = dict(os.environ), os.getcwd(), list(sys.path), set(sys.modules)
    bytecode = sys.dont_write_bytecode
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as empty:
        try:
            os.environ.clear()
            os.environ.update(full_env)
            os.chdir(cwd or empty)
            sys.path[:0] = extra
            sys.dont_write_bytecode = True      # as the command scripts do: no __pycache__ in tests/stubs/
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                try:
                    code = importlib.import_module(MAINS[command]).main([str(a) for a in args])
                except SystemExit as e:         # argparse: --help, or a usage error
                    code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        finally:
            os.environ.clear()
            os.environ.update(environ)
            os.chdir(folder)
            sys.path[:] = path
            sys.dont_write_bytecode = bytecode
            for name in set(sys.modules) - modules:     # the stand-in speech model, so a later test imports afresh
                if any(os.path.abspath(getattr(sys.modules[name], "__file__", None) or "").startswith(
                        os.path.abspath(p) + os.sep) for p in extra):
                    del sys.modules[name]
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def ffstub(tmp_path):
    """Stub ffmpeg and ffprobe (fakemedia.py) first on PATH, logging every call. Returns the environment."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("ffmpeg", "ffprobe"):
        os.symlink(os.path.join(STUBS, "fakemedia.sh"), bin_dir / name)
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
