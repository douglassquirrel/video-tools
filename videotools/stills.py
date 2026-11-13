"""stills: frames of a video file at given times, every so many seconds or where the picture
changes, written singly into a folder with stills.txt and, with --sheet, on labelled contact sheets.

`stills VIDEO (--at T[,T…] | --every SECONDS [--from T] [--until T] | --changes [--threshold N]
[--detect-fps N] [--from T] [--until T]) --out FOLDER [--sheet SHEET.png] [--grid CxR]`, and
`stills VIDEO --sheet SHEET.png --out FOLDER [--grid CxR]` for the sheet of a folder's listing.
Taken in from training-video-tools at fc6091a, its video forms unchanged; its forms that take a
training script stay there. Needs ffmpeg, ffprobe and Pillow.
"""

import argparse

from videotools import cli

PROG = "stills"
SCRIPT_FORMS = ("takes a video file; the forms that take a training script (stills SCRIPT.md …) are "
                "training-video-tools'")


def parser():
    p = argparse.ArgumentParser(prog=PROG, description="Write frames of a video file, chosen by --at, --every or "
                                "--changes, one PNG each at the video's own size into --out with stills.txt "
                                "listing them; with --sheet, also labelled contact sheets. --sheet alone draws "
                                "the sheet of a folder's listing.")
    p.add_argument("VIDEO", help="the video file")
    p.add_argument("--out", metavar="FOLDER", required=True, help="the folder for the stills (never over a file)")
    p.add_argument("--grid", metavar="CxR", default=None, help="columns x rows of a sheet (default: chosen to fit)")
    p.add_argument("--at", metavar="T,T,...", help="frames at these times, in seconds")
    p.add_argument("--every", metavar="SECONDS", type=float, help="a frame every so many seconds from 0")
    p.add_argument("--changes", action="store_true",
                   help="the first frame and every frame where the picture changes (ffmpeg's scene detection)")
    p.add_argument("--threshold", metavar="N",
                   help="with --changes: how big a change counts, 0 to 1 (default 0.3)")
    p.add_argument("--detect-fps", metavar="N",
                   help="with --changes: score the picture N times a second (default 10; less is faster)")
    p.add_argument("--from", dest="start", metavar="T", help="with --every or --changes: only from this time (seconds)")
    p.add_argument("--until", dest="until", metavar="T",
                   help="with --every or --changes: only before this time (seconds); past the end is the end")
    p.add_argument("--sheet", metavar="SHEET.png", help="also a contact sheet of the stills, labelled")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.VIDEO.lower().endswith(".md"):
            raise cli.Failure(f"{args.VIDEO}: stills here {SCRIPT_FORMS}", cli.USAGE)
        from videotools import video_stills
        return video_stills.run(args)
    except cli.Failure as f:
        return cli.report(PROG, f)
