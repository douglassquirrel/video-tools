"""Running ffmpeg and ffprobe: found on PATH, every exit status checked, output parsed.

The formats parsed here were recorded from ffmpeg 9.0.2 (PLAN.md, "Things checked" 6).
Standard library only.
"""

import json
import re
import shutil
import subprocess

from videotools import cli

QUIET = ["-hide_banner", "-loglevel", "error", "-nostdin"]   # -nostdin: never stop to ask about a file


def require(name):
    """The program's path, or Failure (exit 4) saying how to install it."""
    path = shutil.which(name)
    if not path:
        raise cli.Failure(f"{name} is not on PATH; install ffmpeg as the README says", cli.EXTERNAL)
    return path


def run(name, args, doing, partial=None, stdin=None, binary=False, want_stderr=False):
    """Run ffmpeg or ffprobe with `args`; returns its stdout (text, or bytes with `binary`), or its
    stderr with `want_stderr` (where ffmpeg's filters report). A non-zero exit is a Failure (exit 4)
    saying what it was doing, with the program's own output and the file that may be partial.
    Nothing is deleted."""
    program = require(name)
    p = subprocess.run([program] + args, capture_output=True, text=not binary, stdin=stdin)
    if p.returncode != 0:
        tail = f", and {partial} may be partial" if partial else ""
        stderr = p.stderr.decode(errors="replace") if binary else p.stderr
        raise cli.Failure(f"{name} failed (exit {p.returncode}) {doing}; its output follows{tail}\n"
                          + stderr.strip(), cli.EXTERNAL)
    return p.stderr if want_stderr else p.stdout


def audio_samples(path, rate=48000):
    """The file's audio decoded to mono 16-bit at `rate`, as bytes (little-endian)."""
    return run("ffmpeg", QUIET + ["-i", path, "-map", "0:a", "-f", "s16le", "-ac", "1", "-ar", str(rate), "-"],
               f"decoding the audio of {path}", binary=True)


def frame_at(path, seconds, width, height):
    """One frame of the file at `seconds`, as raw RGB bytes of width x height."""
    data = run("ffmpeg", QUIET + ["-ss", f"{seconds:.3f}", "-i", path, "-frames:v", "1", "-f", "rawvideo",
                                  "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-"],
               f"reading the frame of {path} at {seconds:.3f} s", binary=True)
    if len(data) != width * height * 3:
        raise cli.Failure(f"ffmpeg gave {len(data)} bytes for the frame of {path} at {seconds:.3f} s, not the "
                          f"{width * height * 3} of a {width}x{height} frame; is the file that long?", cli.EXTERNAL)
    return data


def scene_report(path, threshold, rate=10, window=None):
    """ffmpeg's report of the frames whose scene-change score is above `threshold` (0 to 1): the
    stderr of `fps=RATE,select='gt(scene,T)',metadata=print` over the whole file, the audio not
    decoded (PLAN.md item 24, 5; item 28, 1: the scoring at `rate` frames a second, a cut reported
    at the first sampled frame after it). With `window` (start, end) in seconds, a seek before the
    input, `-to` the end and `-copyts` so the times stay on the file's clock (item 28, 4)."""
    select = f"fps={rate:g},select='gt(scene,{threshold:g})',metadata=print"
    seek = ["-ss", f"{window[0]:.3f}", "-to", f"{window[1]:.3f}", "-copyts"] if window else []
    return run("ffmpeg", ["-nostdin", "-hide_banner"] + seek + ["-i", path, "-an", "-vf", select, "-f", "null", "-"],
               f"looking for the cuts in {path}", want_stderr=True)


def count_frames(path):
    """The number of video frames in a file, decoded and counted."""
    out = run("ffprobe", ["-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=nb_read_frames", "-of", "json", path], f"counting the frames of {path}")
    return int(json.loads(out)["streams"][0]["nb_read_frames"])


def probe(path):
    """{"duration": seconds, "size": bytes, "fps": float, "width", "height", "frames", "sample_rate",
    "channels"} of a media file, from ffprobe's JSON."""
    out = run("ffprobe", ["-v", "error", "-show_entries", "format=duration,size:stream=index,codec_type,"
                          "nb_frames,r_frame_rate,width,height,sample_rate,channels", "-of", "json", path],
              f"reading {path}")
    data = json.loads(out)
    info = {"duration": float(data["format"]["duration"]), "size": int(data["format"]["size"]),
            "fps": None, "width": None, "height": None, "frames": None, "sample_rate": None, "channels": None}
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and info["fps"] is None:
            num, den = stream.get("r_frame_rate", "0/1").split("/")
            info["fps"] = float(num) / float(den) if float(den) else None
            info["width"], info["height"] = stream.get("width"), stream.get("height")
            info["frames"] = int(stream["nb_frames"]) if stream.get("nb_frames") else None
        elif stream.get("codec_type") == "audio" and info["sample_rate"] is None:
            info["sample_rate"] = int(stream["sample_rate"]) if stream.get("sample_rate") else None
            info["channels"] = stream.get("channels")
    return info


def levels(path):
    """(mean dB, peak dB) of a file's audio, from the volumedetect filter's last report."""
    program = require("ffmpeg")
    p = subprocess.run([program, "-hide_banner", "-i", path, "-map", "0:a", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise cli.Failure(f"ffmpeg failed (exit {p.returncode}) measuring the levels of {path}; its output follows\n"
                          + p.stderr.strip(), cli.EXTERNAL)
    mean = re.findall(r"mean_volume: (-?[\d.]+) dB", p.stderr)
    peak = re.findall(r"max_volume: (-?[\d.]+) dB", p.stderr)
    if not mean or not peak:
        raise cli.Failure(f"ffmpeg's volumedetect gave no levels for {path}; its output follows\n" + p.stderr.strip(),
                          cli.EXTERNAL)
    return float(mean[-1]), float(peak[-1])

