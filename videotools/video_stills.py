"""`stills VIDEO …` (training-video-tools' PLAN.md item 24): frames of a video file at given times, every so many seconds
or where the picture changes, written singly and, with --sheet, on a labelled contact sheet. The
pure parts and the run live here; `stills.py` reads the command line.
"""

import re
import sys

from videotools import cli


def parse_at(text):
    """The times of --at, in seconds, in the order given, each at most once."""
    parts = [p.strip() for p in (text or "").split(",")]
    if not parts or any(p == "" for p in parts):
        raise cli.Failure("--at needs at least one time in seconds, such as 0,1.5,3", cli.USAGE)
    times = []
    for p in parts:
        try:
            t = float(p)
        except ValueError:
            raise cli.Failure(f"--at: '{p}' is not a time in seconds", cli.USAGE) from None
        if t < 0:
            raise cli.Failure(f"--at: a time cannot be negative ({p})", cli.USAGE)
        if t in times:
            raise cli.Failure(f"--at: {p} is given twice", cli.USAGE)
        times.append(t)
    return times


def every_times(step, length, start=0.0):
    """Every `step` seconds from `start` while less than `length`: multiples, so no running sum drifts."""
    if not step > 0:
        raise cli.Failure("--every must be more than 0", cli.USAGE)
    times, i = [], 0
    while round(start + i * step, 6) < length:
        times.append(round(start + i * step, 6))
        i += 1
    return times


def parse_time(text, flag):
    try:
        t = float(text)
    except ValueError:
        raise cli.Failure(f"{flag}: '{text}' is not a time in seconds", cli.USAGE) from None
    if t < 0:
        raise cli.Failure(f"{flag}: a time cannot be negative ({text})", cli.USAGE)
    return t


def parse_window(start_text, end_text, length):
    """(start, end) of --from and --until in seconds: 0 and the length when absent; --from before the
    end, --until after --from and held to the length (training-video-tools' PLAN.md item 28, 3)."""
    start = parse_time(start_text, "--from") if start_text is not None else 0.0
    end = parse_time(end_text, "--until") if end_text is not None else length
    if start >= length:
        raise cli.Failure(f"--from {start:g} s is at or past the end of the video ({length:g} s)", cli.USAGE)
    end = min(end, length)
    if end <= start:
        raise cli.Failure(f"--until ({end:g} s) must be after --from ({start:g} s)", cli.USAGE)
    return start, end


def still_name(seconds):
    """`t0012.40.png`: the time to two decimals, at least four digits before the point, so names sort."""
    return f"t{seconds:07.2f}.png"


def label(seconds):
    return f"{seconds:.2f} s"


def listing_line(seconds):
    """One line of stills.txt: the time, then the file name."""
    return f"{seconds:.2f} {still_name(seconds)}"


def part_name(seconds):
    """The name a still is written under until it is listed: `.t0012.40.png.part`."""
    return f".{still_name(seconds)}.part"


def write_still(img, folder, seconds):
    """Save `img` as the still at `seconds`: to its part name, then its line into stills.txt, then
    the rename, so every still with its name is listed at every moment (training-video-tools' PLAN.md item 29, 1)."""
    import os
    part, final = os.path.join(folder, part_name(seconds)), os.path.join(folder, still_name(seconds))
    img.save(part, format="PNG")        # the part name says nothing about the format
    with open(os.path.join(folder, "stills.txt"), "a", encoding="utf-8") as f:
        f.write(listing_line(seconds) + "\n")
    os.replace(part, final)


DEFAULT_THRESHOLD = 0.3   # ffmpeg's usual scene-change score for a cut; a cut between flat colours scores 0.4
CELL_WIDTH = 360      # a frame's width on the sheet: a vertical Short's frames stay readable
MAX_COLUMNS = 5       # 1800 px across at most


def choose_grid(count):
    """(columns, rows) for `count` frames: the smallest square's side across, at most 5; rows as needed."""
    columns = 1
    while columns * columns < count and columns < MAX_COLUMNS:
        columns += 1
    return columns, -(-count // columns)


def cell_size(width, height):
    """A sheet cell for frames of width x height: 360 wide, the frame's height at that width (rounded up,
    so sheet.frame_size fits the frame at the full 360), plus the strip."""
    from videotools import sheet
    return CELL_WIDTH, -(-CELL_WIDTH * height // width) + sheet.STRIP


def change_times(report, window=None):
    """The first frame, then the `pts_time:` of every frame ffmpeg's `select='gt(scene,T)',metadata=print`
    chose, from its stderr; a frame at 0 is not listed twice. With a `window` (start, end), only the
    times in it, and the first frame only when the window starts at 0 (training-video-tools' PLAN.md item 28, 5)."""
    start, end = window or (0.0, None)
    times = [0.0] if start == 0 else []
    for m in re.finditer(r"\bpts_time:(\S+)", report):
        t = float(m.group(1))
        if t not in times and t >= start and (end is None or t < end):
            times.append(t)
    return times


def parse_grid(text):
    """(columns, rows) of `--grid CxR`, or None when no grid was given."""
    if text is None:
        return None
    try:
        columns, rows = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise cli.Failure(f"--grid should be COLUMNSxROWS, not '{text}'", cli.USAGE) from None
    if columns < 1 or rows < 1:
        raise cli.Failure(f"--grid needs at least one column and one row, not '{text}'", cli.USAGE)
    return columns, rows


DEFAULT_DETECT_FPS = 10   # the scoring's rate, frames a second: a cut lasts longer than a tenth of a second


def parse_detect_fps(text):
    try:
        value = float(text)
    except ValueError:
        value = 0.0
    if not value > 0:
        raise cli.Failure(f"--detect-fps should be a number above 0, not '{text}'", cli.USAGE)
    return value


def parse_threshold(text):
    try:
        value = float(text)
    except ValueError:
        value = -1.0
    if not 0 <= value <= 1:
        raise cli.Failure(f"--threshold should be a number from 0 to 1, not '{text}'", cli.USAGE)
    return value


def read_listing(path):
    """The (time, name) of every line of a stills.txt, as written by listing_line; refused in words
    when it is missing or a line is not `TIME NAME` (training-video-tools' PLAN.md item 28, 7)."""
    import os
    if not os.path.isfile(path):
        raise cli.Failure(f"{path} is missing; --sheet alone draws the stills a folder's listing names")
    entries = []
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            parts = raw.split()
            try:
                if len(parts) != 2:
                    raise ValueError
                entries.append((float(parts[0]), parts[1]))
            except ValueError:
                raise cli.Failure(f"{path}: line {n} is not 'TIME NAME': {raw.rstrip()}") from None
    return entries


def stills_said(count):
    return f"{count} still" if count == 1 else f"{count} stills"


def sheet_of_folder(args):
    """`stills VIDEO --sheet SHEET.png --out FOLDER`: the sheet of every still FOLDER/stills.txt lists,
    in that order, read from the PNGs; nothing is read from the video (training-video-tools' PLAN.md item 28, 7)."""
    import os
    video, folder = args.VIDEO, args.out
    grid = parse_grid(args.grid)
    cli.refuse_existing(args.sheet)
    if not os.path.isfile(video):
        raise cli.Failure(f"{video} is missing")
    listing = os.path.join(folder, "stills.txt")
    entries = read_listing(listing)
    if not entries:
        raise cli.Failure(f"{listing} lists no stills; there is nothing to draw")
    for _, name in entries:
        if not os.path.isfile(os.path.join(folder, name)):
            raise cli.Failure(f"{listing} names {name}, which is not in {folder}")
    cli.need("PIL")
    from PIL import Image
    images = [Image.open(os.path.join(folder, name)).convert("RGB") for _, name in entries]
    width, height = images[0].size
    sheets = Sheets(args.sheet, grid, len(entries), width, height)
    for i, ((t, _), img) in enumerate(zip(entries, images)):
        sheets.add(i, img, label(t))
    sheets.save()
    print(f"Drew {stills_said(len(entries))} from {listing} on" + sheets.said()[len(" and"):])
    return 0


def run(args):
    """`stills VIDEO …`: the frames chosen, written singly into --out and listed in stills.txt."""
    import os

    from videotools import ffmpeg
    video, folder = args.VIDEO, args.out
    modes = [f for f, on in (("--at", args.at is not None), ("--every", args.every is not None),
                             ("--changes", args.changes)) if on]
    windowed = args.start is not None or args.until is not None
    if not modes and windowed:
        raise cli.Failure("--from and --until need --every or --changes (--sheet alone draws a folder's listing)",
                          cli.USAGE)
    if not modes and args.sheet:
        return sheet_of_folder(args)
    if not modes:
        raise cli.Failure("choose how to pick the frames of a video file: --at, --every or --changes", cli.USAGE)
    if len(modes) > 1:
        raise cli.Failure(f"give one of --at, --every and --changes, not {' and '.join(modes)}", cli.USAGE)
    if windowed and args.at is not None:
        raise cli.Failure("--from and --until go with --every or --changes, not --at", cli.USAGE)
    for text, flag in ((args.start, "--from"), (args.until, "--until")):
        if text is not None:
            parse_time(text, flag)              # a bad time is refused before anything runs
    if args.threshold is not None and not args.changes:
        raise cli.Failure("--threshold goes with --changes", cli.USAGE)
    threshold = parse_threshold(args.threshold) if args.threshold is not None else DEFAULT_THRESHOLD
    if args.detect_fps is not None and not args.changes:
        raise cli.Failure("--detect-fps goes with --changes", cli.USAGE)
    detect_fps = parse_detect_fps(args.detect_fps) if args.detect_fps is not None else DEFAULT_DETECT_FPS
    if args.every is not None and not args.every > 0:
        raise cli.Failure("--every must be more than 0", cli.USAGE)
    at = parse_at(args.at) if args.at is not None else None
    grid = parse_grid(args.grid)
    if args.sheet:
        cli.refuse_existing(args.sheet)
    ffmpeg.require("ffmpeg")
    ffmpeg.require("ffprobe")
    cli.need("PIL")
    from PIL import Image
    info = ffmpeg.probe(video)
    length, width, height = info["duration"], info["width"], info["height"]
    window = parse_window(args.start, args.until, length) if windowed else None
    listing = os.path.join(folder, "stills.txt")
    if not window:
        cli.refuse_existing(listing)    # before the scan: nothing is read for a run that will be refused
    if args.changes:
        times = change_times(ffmpeg.scene_report(video, threshold, detect_fps, window), window)
    elif args.every is not None:
        times = every_times(args.every, window[1] if window else length, window[0] if window else 0.0)
    else:
        times = at
    for t in times:
        if t >= length:
            raise cli.Failure(f"{t:g} s is past the end of {video} ({length:.3f} s)", cli.USAGE)
    stills = [(t, os.path.join(folder, still_name(t))) for t in times]
    listed = {name for _, name in read_listing(listing)} if os.path.isfile(listing) else set()
    for _, path in stills:                  # training-video-tools' item 29, 2: in a window, an unlisted still is a kill's leftover
        if window and os.path.basename(path) not in listed and os.path.lexists(path):
            sys.stderr.write(f"stills: {os.path.basename(path)} was there but not listed; written again\n")
        else:
            cli.refuse_existing(path)
    sheets = Sheets(args.sheet, grid, len(times), width, height) if args.sheet else None
    os.makedirs(folder, exist_ok=True)
    for i, (t, path) in enumerate(stills):
        data = ffmpeg.frame_at(video, t, width, height)
        img = Image.frombytes("RGB", (width, height), data)
        write_still(img, folder, t)         # a line at a time, the still named only once listed
        if sheets:
            sheets.add(i, img, label(t))
        print(f"{os.path.basename(path)} at {t:.3f} s")
    if sheets:
        sheets.save()
    print(f"Wrote {stills_said(len(stills))} to {folder}" + (sheets.said() if sheets else ""))
    return 0


class Sheets:
    """The contact sheet(s) of a run: cells 360 wide in the video's proportions, `grid` (or one
    chosen to fit) per sheet, as many sheets as the frames need; each frame pasted as it is read,
    its time in the strip under it. Every sheet's name is refused before any is read."""

    def __init__(self, out, grid, count, width, height):
        from PIL import Image, ImageDraw, ImageFont

        from videotools import sheet
        self.columns, self.rows = grid or choose_grid(count)
        self.cell = cell_size(width, height)
        self.per_sheet = self.columns * self.rows
        self.paths = sheet.names(out, -(-count // self.per_sheet))
        for path in self.paths:
            cli.refuse_existing(path)
        self.images = [Image.new("RGB", (self.columns * self.cell[0], self.rows * self.cell[1]), "white")
                       for _ in self.paths]
        self.draws = [ImageDraw.Draw(im) for im in self.images]
        self.font = ImageFont.load_default(size=sheet.LABEL_SIZE)
        self.paste = sheet.paste

    def add(self, index, img, text):
        which, where = divmod(index, self.per_sheet)
        x, y = (where % self.columns) * self.cell[0], (where // self.columns) * self.cell[1]
        self.paste(self.images[which], self.draws[which], img, x, y, self.cell, text, self.font)

    def save(self):
        for im, path in zip(self.images, self.paths):
            im.save(path)

    def said(self):
        if len(self.paths) == 1:
            return f" and the sheet {self.paths[0]}"
        return f" and {len(self.paths)} sheets {', '.join(self.paths)}"
