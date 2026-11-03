"""Tier 2: the command against stubs of ffmpeg and ffprobe, in its own temporary folders."""

import hashlib
import json
import os
import subprocess
import sys

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
