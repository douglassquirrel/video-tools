"""cut-video: cut the beginning and end off a video at phrases found in its transcript (PLAN.md, cut-video)."""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

from videotools.cut import CutError, clock, cut_cues, ffmpeg_args, locate, plain_text
from videotools.match import words
from videotools.srt import SrtError, format_srt, parse_srt


class Refusal(Exception):
    """Something the command will not or cannot do: `code` is its exit code, `message` says what to do."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="cut-video",
        description="Cut the beginning and end off a video at phrases found in its transcript, and cut the "
                    "transcript to match. Writes STEM-cut.mp4, STEM-cut.srt and STEM-cut.txt into DIR.")
    p.add_argument("--dry-run", action="store_true",
                   help="find the phrases and say what would be cut and how, writing nothing")
    p.add_argument("--from", dest="from_phrase", metavar="PHRASE",
                   help="cut from the start of the caption where this phrase begins (default: keep the beginning)")
    p.add_argument("--to", dest="to_phrase", metavar="PHRASE",
                   help="cut to the end of the caption where this phrase ends (default: keep the end)")
    p.add_argument("--out", required=True, metavar="DIR", help="the folder to write into (made if missing)")
    p.add_argument("video", metavar="VIDEO", help="the video to cut; only read")
    p.add_argument("transcript", metavar="TRANSCRIPT", help="its SubRip (.srt) transcript; only read")
    args = p.parse_args(argv)
    if args.from_phrase is None and args.to_phrase is None:
        p.error("give --from PHRASE, --to PHRASE or both: with neither there is nothing to cut")
    for flag, phrase in (("--from", args.from_phrase), ("--to", args.to_phrase)):
        if phrase is not None and not words(phrase):
            p.error(f'the {flag} phrase "{phrase}" has no words to look for')
    return args


def readable(what, path):
    """Refuse unless `path` can be opened for reading."""
    try:
        with open(path, "rb"):
            pass
    except OSError as e:
        reason = e.strerror.lower()
        raise Refusal(3, f"cannot read the {what} {path}: {reason}. Check the path.")


def read_cues(path):
    """The transcript's cues, or a Refusal saying what is wrong with it."""
    readable("transcript", path)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise Refusal(3, f"the transcript {path} is not UTF-8 text. Save it as UTF-8 and try again.")
    try:
        cues = parse_srt(text)
    except SrtError as e:
        raise Refusal(4, f"the transcript {path} is not a SubRip (.srt) file I can read: line {e.line}: {e.message}")
    if not cues:
        raise Refusal(4, f"the transcript {path} holds no cues, so there is nothing to find a phrase in.")
    return cues


def installed():
    """Refuse unless ffmpeg and ffprobe are on PATH."""
    for program in ("ffmpeg", "ffprobe"):
        if shutil.which(program) is None:
            raise Refusal(8, f"{program} is not installed (or not on PATH). Install it with: brew install ffmpeg")


def one_line(text):
    return " / ".join(line.strip() for line in text.strip().splitlines())


def duration(video):
    """The video's length in milliseconds, from ffprobe."""
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", video], capture_output=True, text=True, check=False)
    if p.returncode != 0:
        raise Refusal(10, f"ffprobe could not read {video} as a video: {one_line(p.stderr)}")
    try:
        return round(float(p.stdout.strip()) * 1000)
    except ValueError:
        raise Refusal(10, f"ffprobe gave no duration for {video} ({p.stdout.strip()!r}), so it cannot be cut.")


def output_folder(out, names):
    """Refuse if `out` is not a folder, or already holds any of `names`."""
    if os.path.exists(out) and not os.path.isdir(out):
        raise Refusal(9, f"cannot make the output folder {out}: file exists. Give another --out.")
    for name in names:
        path = os.path.join(out, name)
        if os.path.lexists(path):
            raise Refusal(9, f"{path} already exists, and nothing is ever written over. Move it, or give another "
                             "--out.")


def main(argv=None):
    try:
        args = parse_args(argv)
    except SystemExit as e:
        return e.code
    try:
        return cut_video(args)
    except Refusal as e:
        sys.stderr.write(f"cut-video: {e.message}\n")
        return e.code
    except KeyboardInterrupt:
        sys.stderr.write("cut-video: stopped, so nothing was written.\n")
        return 130


def context(cues, at):
    """Cue `at` (marked) with the one before and the one after, numbered from 1 as in the transcript."""
    return ["  {} {:>3}  {} --> {}  {}".format(">" if i == at else " ", i + 1, clock(cues[i].start),
                                                clock(cues[i].end), " ".join(cues[i].lines))
            for i in range(max(at - 1, 0), min(at + 2, len(cues)))]


def dry_run(args, cues, cut, length, names, video):
    """Say where the cut falls and how it would be made."""
    if args.from_phrase is None:
        print("Start: 00:00:00.000, the beginning of the video (no --from)")
    else:
        print(f'Start: {clock(cut.start)}, the start of cue {cut.first + 1} (--from "{args.from_phrase}")')
        print("\n".join(context(cues, cut.first)))
    if args.to_phrase is None:
        print(f"End: {clock(cut.end)}, the end of the video (no --to)")
    else:
        where = "the end of cue {}" if cut.end == cues[cut.last].end else "the end of the video, inside cue {}"
        print(f"End: {clock(cut.end)}, {where.format(cut.last + 1)} (--to \"{args.to_phrase}\")")
        print("\n".join(context(cues, cut.last)))
    print(f"Length: {clock(cut.end - cut.start)} of the video's {clock(length)}, {cut.last - cut.first + 1} cues.")
    print(f"Would write {os.path.join(args.out, names[0])}, {names[1]} and {names[2]}.")
    print("ffmpeg command (the video is written under a temporary name, renamed when complete):")
    print("  " + shlex.join(ffmpeg_args(video, cut, os.path.join(os.path.abspath(args.out), names[0]))))
    print("Dry run: nothing written.")
    return 0


def cut_video(args):
    video = os.path.abspath(args.video)
    readable("video", args.video)
    cues = read_cues(args.transcript)
    installed()
    length = duration(video)
    try:
        cut = locate(cues, args.from_phrase, args.to_phrase, length)
    except CutError as e:
        raise Refusal(e.code, e.message)
    kept = cut_cues(cues, cut)
    stem = os.path.splitext(os.path.basename(video))[0] + "-cut"
    names = [stem + ".mp4", stem + ".srt", stem + ".txt"]
    output_folder(args.out, names)
    if args.dry_run:
        return dry_run(args, cues, cut, length, names, video)
    try:
        os.makedirs(args.out, exist_ok=True)
    except OSError as e:
        raise Refusal(9, f"cannot make the output folder {args.out}: {e.strerror.lower()}. Give another --out.")
    temps = []
    try:
        for name in names:
            fd, temp = tempfile.mkstemp(prefix="." + name + ".", suffix=".part", dir=os.path.abspath(args.out))
            os.close(fd)
            temps.append(temp)
        p = subprocess.run(ffmpeg_args(video, cut, temps[0]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, text=True, check=False)
        if p.returncode != 0:
            raise Refusal(11, f"ffmpeg failed (exit {p.returncode}), so nothing was written: {one_line(p.stderr)}")
        for temp, text in zip(temps[1:], (format_srt(kept), plain_text(kept))):
            with open(temp, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        print(f"Cut {clock(cut.start)} to {clock(cut.end)} ({clock(cut.end - cut.start)} long), {len(kept)} cues.")
        for temp, name in zip(temps, names):
            os.replace(temp, os.path.join(args.out, name))
            print("Wrote " + os.path.join(args.out, name))
    finally:
        for temp in temps:
            if os.path.exists(temp):
                os.unlink(temp)
    return 0
