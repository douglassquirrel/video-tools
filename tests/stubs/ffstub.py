"""A stand-in for ffmpeg and ffprobe in Tier 2 tests (conftest.py puts one of each on PATH).

Every call is logged as a line of JSON to $FFSTUB_LOG: {"name": "ffmpeg" or "ffprobe", "args": [...]}.
ffprobe prints $FFPROBE_OUTPUT (default "26.000000") and exits 0, or exits $FFPROBE_EXIT with a message.
ffmpeg writes a few bytes to its last argument and exits 0; with $FFMPEG_EXIT set it writes part of a file,
prints a message and exits with that code.
"""

import json
import os
import sys

name = os.environ["FFSTUB_NAME"]
args = sys.argv[1:]
with open(os.environ["FFSTUB_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"name": name, "args": args}) + "\n")

if name == "ffprobe":
    code = int(os.environ.get("FFPROBE_EXIT", "0"))
    if code:
        sys.stderr.write(f"{args[-1]}: Invalid data found when processing input\n")
        sys.exit(code)
    print(os.environ.get("FFPROBE_OUTPUT", "26.000000"))
else:
    code = int(os.environ.get("FFMPEG_EXIT", "0"))
    with open(args[-1], "wb") as out:
        out.write(b"partial" if code else b"stub mp4")
    if code:
        sys.stderr.write("Conversion failed!\n")
    sys.exit(code)
