"""A stand-in for ffmpeg and ffprobe with fake media, for stills VIDEO, compare-video and narrate
(tests/tier2/conftest.py's `ffstub` fixture puts both names on PATH). Taken in from training-video-tools'
tests/stubs/ffstub.py at fc6091a, cut to the jobs these commands give it; cut-video has its own stub,
ffstub.py.

Media files are fake: text files of `key=value` lines (`frames=90`, `duration=3.0`,
`max_volume=-1.2`, `mean_volume=-20.0`, `tone=0-1.0,2.0-3.0` the spans where the decoded audio is
loud, `colours=0:200.40.40,10:0.0.255` the colour of every frame from each time, `width=480`,
`height=854` the frame size, default 1920x1080, `scenes=2,4.04` the times the scene scan reports,
`unstated_frames=1` a video stream that does not state its frame count, `no_levels=1` a volumedetect
report without levels, `early_report=1` an earlier volumedetect report before the last).
Every call is appended as a JSON line to FFSTUB_LOG. FFSTUB_FAIL names a job (`probe`, `volume`,
`frame`, `frame@T` (the frame read at -ss T only), `scenes`, `audio`) that exits 1; FFSTUB_SHORT_FRAME
makes a frame read give half the bytes. An existing
output is refused unless `-y` is given, as ffmpeg does. Nothing here is real ffmpeg output beyond
its format.
"""

import json
import os
import struct
import sys


def read_fake(path):
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    out[k] = v
    except OSError:
        pass
    return out


def write_fake(path, fields):
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(f"{k}={v}\n" for k, v in fields.items())


def log(entry):
    with open(os.environ["FFSTUB_LOG"], "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def arg_after(args, flag, default=None):
    return args[args.index(flag) + 1] if flag in args else default


def fail_if(job, output=None):
    if os.environ.get("FFSTUB_FAIL") == job:
        if output:
            write_fake(output, {"partial": "yes"})
        sys.stderr.write(f"stub ffmpeg: {job} failed on purpose\n")
        sys.exit(1)


def ffprobe(args):
    path = args[-1]
    fake = read_fake(path)
    if not fake:
        sys.stderr.write(f"{path}: No such file or directory\n")
        return 1
    fail_if("probe")
    entries = arg_after(args, "-show_entries", "")
    if "nb_read_frames" in entries:
        print(json.dumps({"programs": [], "stream_groups": [],
                          "streams": [{"nb_read_frames": fake.get("frames", "0")}]}, indent=4))
    else:
        print(json.dumps({"programs": [], "stream_groups": [],
                          "streams": [{"index": 0, "codec_type": "video", "width": int(fake.get("width", 1920)),
                                       "height": int(fake.get("height", 1080)),
                                       "r_frame_rate": "30/1", "nb_frames": fake.get("frames", "0")}
                                      if not fake.get("unstated_frames") else
                                      {"index": 0, "codec_type": "video", "width": int(fake.get("width", 1920)),
                                       "height": int(fake.get("height", 1080)), "r_frame_rate": "30/1"},
                                      {"index": 1, "codec_type": "audio", "sample_rate": "48000", "channels": 1,
                                       "r_frame_rate": "0/0", "nb_frames": "1"}],
                          "format": {"duration": fake.get("duration", "0"), "size": str(os.path.getsize(path))}},
                         indent=4))
    return 0


def ffmpeg(args):
    output = args[-1]
    af = arg_after(args, "-af", "")
    if output != "-" and os.path.exists(output) and "-y" not in args:
        # As ffmpeg does: it asks on a terminal, and with -nostdin (or no terminal) gives up.
        sys.stderr.write(f"File '{output}' already exists. Overwrite? [y/N] Not overwriting - exiting\n")
        return 1
    if "volumedetect" in af:
        fail_if("volume")
        fake = read_fake(arg_after(args, "-i"))
        sys.stderr.write("[Parsed_volumedetect_0 @ 0x1] n_samples: 0\n")
        if fake.get("no_levels"):               # a report without the two lines
            return 0
        if fake.get("early_report"):            # an earlier report first: the last one counts
            sys.stderr.write("[Parsed_volumedetect_0 @ 0x1] mean_volume: -91.0 dB\n"
                             "[Parsed_volumedetect_0 @ 0x1] max_volume: -91.0 dB\n")
        sys.stderr.write(f"[Parsed_volumedetect_0 @ 0x2] n_samples: 144000\n"
                         f"[Parsed_volumedetect_0 @ 0x2] mean_volume: {fake.get('mean_volume', '-20.0')} dB\n"
                         f"[Parsed_volumedetect_0 @ 0x2] max_volume: {fake.get('max_volume', '-1.0')} dB\n")
        return 0
    if "metadata=print" in arg_after(args, "-vf", ""):   # the scene scan: the shape ffmpeg 9.0.2 printed
        fail_if("scenes")
        fake = read_fake(arg_after(args, "-i"))
        # A seek before -i (training-video-tools' item 28): only the cuts in [-ss, -to) are seen; times stay on the file's
        # clock only with -copyts, as real ffmpeg does (training-video-tools' "Things checked").
        before = args[:args.index("-i")]
        start, end = float(arg_after(before, "-ss", "0")), float(arg_after(before, "-to", "1e9"))
        cuts = [float(v) for v in fake.get("scenes", "").split(",") if v]
        cuts = [t if "-copyts" in before else t - start for t in cuts if start <= t < end]
        for i, t in enumerate(f"{t:g}" for t in cuts):
            sys.stderr.write(f"[Parsed_metadata_1 @ 0x7a0c62280] frame:{i}    pts:{int(float(t) * 12800)}   pts_time:{t}\n"
                             f"[Parsed_metadata_1 @ 0x7a0c62280] lavfi.scene_score=0.400000\n")
        return 0
    if "-frames:v" in args:
        fail_if("frame")
        if os.environ.get("FFSTUB_FAIL") == "frame@" + arg_after(args, "-ss", "0"):   # one chosen frame fails
            fail_if("frame@" + arg_after(args, "-ss", "0"))
        if output == "-":                       # one raw rgb24 frame of the colour at -ss
            fake = read_fake(arg_after(args, "-i"))
            at = float(arg_after(args, "-ss", "0"))
            colour = (200, 40, 40)
            for entry in fake.get("colours", "").split(","):
                if entry and float(entry.split(":")[0]) <= at:
                    colour = tuple(int(v) for v in entry.split(":")[1].split("."))
            width, height = (int(v) for v in arg_after(args, "-s", "1920x1080").split("x"))
            frame = bytes(colour) * (width * height)
            if os.environ.get("FFSTUB_SHORT_FRAME"):    # as ffmpeg gives at a time past the last frame
                frame = frame[:len(frame) // 2]
            sys.stdout.buffer.write(frame)
            return 0
    if "-f" in args and arg_after(args, "-f") == "s16le":   # the audio decoded: loud in the tone spans
        fail_if("audio")
        fake = read_fake(arg_after(args, "-i"))
        rate = int(arg_after(args, "-ar", "48000"))
        total = round(float(fake.get("duration", "0")) * rate)
        loud = struct.pack("<h", 3277)          # about -20 dBFS
        out = bytearray(total * 2)
        for span in [v for v in fake.get("tone", "").split(",") if v]:
            a, b = (round(float(v) * rate) for v in span.split("-"))
            out[a * 2:b * 2] = loud * (b - a)
        sys.stdout.buffer.write(out)
        return 0
    sys.stderr.write(f"stub ffmpeg: unexpected arguments {args}\n")
    return 2


def main():
    name = os.environ.get("FFSTUB_NAME") or os.path.basename(sys.argv[0])
    args = sys.argv[1:]
    log({name: args})
    sys.exit(ffprobe(args) if name == "ffprobe" else ffmpeg(args))


if __name__ == "__main__":
    main()
