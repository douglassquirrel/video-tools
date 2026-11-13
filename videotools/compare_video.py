"""compare-video: two finished videos compared on length, frames, levels, envelopes and pictures.

`compare-video NEW.mp4 OLD.mp4 [--every SECONDS] [--sheet OUT.png]`: each file's duration, frame
count, peak and mean level; the correlation of the two narration envelopes (0.1 s windows of the
mono mix) and the windows that are speech in one and silence in the other; the mean absolute
difference of the frames every --every seconds (default 5), with the mean, the median and the
five largest; with --sheet, those five pairs side by side (new left, old right), labelled under
each. Reports, never judges: exit 0. Needs ffmpeg, ffprobe and numpy (and Pillow for the sheet).
"""

import argparse
import os

from videotools import cli, ffmpeg

PROG = "compare-video"
RATE = 48000              # the mono mix is decoded at this rate
WINDOW = 0.1              # seconds per envelope window
SPEECH_DBFS = -40         # a window above this is speech
FULL_SCALE = 32768        # 16-bit
LARGEST = 5
FRAME_WIDTH = 950         # on the sheet: two frames a row, a gap between


def parser():
    p = argparse.ArgumentParser(prog=PROG, description="Compare two finished videos: length, frames, levels, "
                                "narration envelopes and frames every few seconds. Reports; never judges.")
    p.add_argument("NEW", help="the new (or re-made) video")
    p.add_argument("OLD", help="the earlier video to compare it with")
    p.add_argument("--every", metavar="SECONDS", type=float, default=5.0,
                   help="compare a frame from each file every so many seconds (default 5)")
    p.add_argument("--sheet", metavar="OUT.png", help="write the five most different pairs side by side "
                   "(never over a file)")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        return _run(args)
    except cli.Failure as f:
        return cli.report(PROG, f)


# ---- the measures (numpy, pure)

def envelope(samples, rate, window=WINDOW):
    """The RMS of each whole window of `samples` (int16 or float), as floats."""
    import numpy as np
    n = int(round(rate * window))
    whole = (len(samples) // n) * n
    blocks = np.asarray(samples[:whole], dtype=np.float64).reshape(-1, n)
    return np.sqrt((blocks * blocks).mean(axis=1))


def correlation(a, b):
    """Pearson's correlation of two envelopes over the shorter length; None when either is flat."""
    import numpy as np
    n = min(len(a), len(b))
    a, b = np.asarray(a[:n], dtype=np.float64), np.asarray(b[:n], dtype=np.float64)
    if n < 2 or a.std() == 0 or b.std() == 0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def is_speech(env):
    import numpy as np
    return np.asarray(env) > FULL_SCALE * 10 ** (SPEECH_DBFS / 20)


def disagreements(a, b):
    """(windows that are speech in one envelope and silence in the other, windows compared)."""
    n = min(len(a), len(b))
    return int((is_speech(a[:n]) != is_speech(b[:n])).sum()), n


def summarise(diffs):
    """(mean, median, the five largest (time, difference) largest first, ties by time) of
    [(time, difference)]."""
    import numpy as np
    values = [d for _, d in diffs]
    largest = sorted(diffs, key=lambda td: (-td[1], td[0]))[:LARGEST]
    return float(np.mean(values)), float(np.median(values)), largest


# ---- the command

def describe(path):
    info = ffmpeg.probe(path)
    frames = info["frames"] if info["frames"] is not None else ffmpeg.count_frames(path)
    mean, peak = ffmpeg.levels(path)
    return {"duration": info["duration"], "frames": frames, "peak": peak, "mean": mean,
            "width": info["width"] or 1920, "height": info["height"] or 1080}


def _run(args):
    if not args.every > 0:
        raise cli.Failure("--every must be more than 0", cli.USAGE)
    if args.sheet:
        cli.refuse_existing(args.sheet)
    np = cli.need("numpy")
    if args.sheet:
        cli.need("PIL")
    for path in (args.NEW, args.OLD):
        if not os.path.isfile(path):
            raise cli.Failure(f"no such file: {path}")
    ffmpeg.require("ffmpeg")
    ffmpeg.require("ffprobe")
    files = {}
    for label, path in (("NEW", args.NEW), ("OLD", args.OLD)):
        files[label] = describe(path)
        f = files[label]
        print(f"{label} {path}\n  length {f['duration']:.3f} s, {f['frames']} frames; "
              f"peak {f['peak']:.1f} dBFS, mean {f['mean']:.1f} dBFS", flush=True)
    envs = [envelope(np.frombuffer(ffmpeg.audio_samples(p, RATE), dtype="<i2"), RATE) for p in (args.NEW, args.OLD)]
    corr = correlation(*envs)
    count, compared = disagreements(*envs)
    shown = f"{corr:.4f}" if corr is not None else "undefined (a flat envelope)"
    print(f"narration envelopes ({WINDOW:g} s windows, {compared} compared): correlation {shown}; "
          f"speech in one and silence in the other: {count} windows", flush=True)
    width, height = files["NEW"]["width"], files["NEW"]["height"]
    shorter = min(files["NEW"]["duration"], files["OLD"]["duration"])
    diffs, frames = [], {}
    t = 0.0
    while t < shorter:
        pair = [ffmpeg.frame_at(p, t, width, height) for p in (args.NEW, args.OLD)]
        a, b = (np.frombuffer(d, dtype=np.uint8).astype(np.int16) for d in pair)
        diffs.append((t, float(np.abs(a - b).mean())))
        if args.sheet:
            frames[t] = pair
        t += args.every
    mean, median, largest = summarise(diffs)
    print(f"frames every {args.every:g} s ({len(diffs)} pairs): mean difference {mean:.1f}, "
          f"median {median:.1f} (0-255)")
    print("  largest: " + ", ".join(f"{d:.1f} at {t:.1f} s" for t, d in largest))
    if args.sheet:
        sheet(args.sheet, largest, frames, width, height)
        print(f"sheet of {len(largest)} pairs written to {args.sheet}")
    return cli.OK


def sheet(path, largest, frames, width, height):
    """The largest pairs, one a row, new left and old right, each labelled under the frame."""
    from PIL import Image, ImageDraw, ImageFont

    from videotools import sheet as sheet_
    cell = (FRAME_WIDTH, FRAME_WIDTH * height // width + sheet_.STRIP)
    gap = sheet_.SHEET[0] - 2 * FRAME_WIDTH
    out = Image.new("RGB", (sheet_.SHEET[0], cell[1] * len(largest)), sheet_.STRIP_FILL)
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(sheet_.LABEL_SIZE)
    for row, (t, d) in enumerate(largest):
        new, old = (Image.frombytes("RGB", (width, height), data) for data in frames[t])
        y = row * cell[1]
        sheet_.paste(out, draw, new, 0, y, cell, f"NEW  {t:.1f} s", font)
        sheet_.paste(out, draw, old, FRAME_WIDTH + gap, y, cell, f"OLD  {t:.1f} s   mean difference {d:.1f}", font)
    out.save(path)
