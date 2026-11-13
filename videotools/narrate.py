"""narrate --lines: each line of a description table spoken to its own clip with the local Kokoro
model, and timing.json.

`narrate --lines TABLE.md --out FOLDER [--speed S] [--voice V] [--replace] [--dry-run [--phonemes]]`:
reads the table (`lines.py`) and the config, speaks each line's `Say` (or its `Line`) through
kokoro-onnx, trims the silence, and writes `NN.wav` for each line and `timing.json` into --out.
Refuses to write over anything unless --replace. Taken in from training-video-tools at fc6091a, its
--lines form unchanged; its form that takes a training script stays there. Needs numpy, soundfile
and kokoro-onnx, imported only when a real run starts.
"""

import argparse
import json
import os
import sys

from videotools import cli, config, phonemes
from videotools import lines as lines_

PROG = "narrate"
LINES_SPEED = 1.5       # --lines' default: chosen by ear from the samples (Squirrel, 17 October 2026)
THRESHOLD = 0.01        # a sample above this is sound
BEFORE, AFTER = 0.03, 0.08  # seconds kept before the first and after the last sound
LINES_LANG = "en-us"
PHONEMES_DRY_RUN = "--phonemes goes with --dry-run (it only shows what the voice would be given)"
SCRIPT_FORM = ("narrate here takes --lines TABLE.md --out FOLDER; the form that takes a training script "
               "(narrate SCRIPT.md) is training-video-tools'")


def trim(samples, rate):
    """The clip without its leading and trailing silence, keeping 30 ms before the first and
    80 ms after the last sample above the threshold; an all-silent clip is returned whole."""
    import numpy as np
    loud = np.where(np.abs(samples) > THRESHOLD)[0]
    if not len(loud):
        return samples
    return samples[max(0, loud[0] - int(BEFORE * rate)): loud[-1] + 1 + int(AFTER * rate)]


def parser():
    p = argparse.ArgumentParser(prog=PROG, description="Speak each line of a description table with the local "
                                "speech model, one clip per line, and write the clip lengths to timing.json. The "
                                "settings are read from ~/.video-tools.conf; flags win over them.")
    p.add_argument("--lines", metavar="TABLE.md",
                   help="a Markdown table of description lines ('#', 'Start (s)', 'Line', and optionally 'Say', "
                        "spoken instead of 'Line', [[…]] spans allowed), each spoken to its own clip in --out")
    p.add_argument("--out", metavar="FOLDER", help="the folder for the clips and timing.json")
    p.add_argument("--voice", help="the voice, e.g. af_heart (default: VOICE in the config, else af_heart)")
    p.add_argument("--speed", type=float, help="the speed (default 1.5, within the model's 0.5 to 2.0)")
    p.add_argument("--replace", action="store_true",
                   help="write over existing clips and timing.json, listing them first")
    p.add_argument("--phonemes", action="store_true",
                   help="with --dry-run: also print the phoneme string each cue or line would be given, [[…]] spans "
                        "spliced in")
    p.add_argument("--dry-run", action="store_true",
                   help="list the lines, the voice and an estimate of each clip; write nothing")
    return p


def _model_dir(conf):
    """The folder holding model.onnx and voices.npz, from SPEECH_MODEL_DIR."""
    folder = conf.get("SPEECH_MODEL_DIR")
    if not folder:
        raise cli.Failure(f"SPEECH_MODEL_DIR is not set in {config.path()}; see the README's one-time set-up")
    model, voices = os.path.join(folder, "model.onnx"), os.path.join(folder, "voices.npz")
    if not (os.path.isfile(model) and os.path.isfile(voices)):
        raise cli.Failure(f"no model.onnx and voices.npz in {folder} (SPEECH_MODEL_DIR in {config.path()}); "
                          "see the README's one-time set-up")
    return model, voices


def _load_model(model, voices):
    return cli.need("kokoro_onnx").Kokoro(model, voices)


def main(argv=None):
    p = parser()
    args, extra = p.parse_known_args(argv)
    if extra and any(x.startswith("-") for x in extra):
        p.error("unrecognized arguments: " + " ".join(extra))
    try:
        if extra:
            raise cli.Failure(f"{extra[0]}: {SCRIPT_FORM}", cli.USAGE)
        if args.lines is None:
            raise cli.Failure("give --lines TABLE.md --out FOLDER", cli.USAGE)
        return _run_lines(args)
    except (cli.Failure, config.ConfigError) as f:
        return cli.report(PROG, cli.Failure(str(f), getattr(f, "code", cli.REFUSED)))


def _phonemizer(lang):
    """text -> phonemes, through the model's own tokenizer (espeak), as create() would; needs
    the speech package (the usual one line if it is missing) but not the model file."""
    import importlib
    cli.need("kokoro_onnx")
    tokenizer = importlib.import_module("kokoro_onnx.tokenizer").Tokenizer()
    return lambda text: tokenizer.phonemize(text, lang)


def for_voice(said, phonemize):
    """The phoneme string the voice is given for what a cue or line says: text parts phonemized,
    [[…]] spans as they stand, spaces as written, then the lead-in (item 30, 1)."""
    return phonemes.lead_in(phonemes.splice(said, phonemize))


def _run_lines(args):
    """`narrate --lines TABLE.md --out FOLDER --speed S`: each line of the table to its own clip."""
    if args.out is None:
        raise cli.Failure("--lines needs --out FOLDER for the clips", cli.USAGE)
    if args.phonemes and not args.dry_run:
        raise cli.Failure(PHONEMES_DRY_RUN, cli.USAGE)
    speed = lines_.check_speed(args.speed if args.speed is not None else LINES_SPEED)
    conf = config.read()
    voice = args.voice or conf.get("VOICE", "") or "af_heart"
    model, voices = _model_dir(conf)
    rows = lines_.read(args.lines)
    folder, timing_path = args.out, os.path.join(args.out, "timing.json")
    largest = max(line["n"] for line in rows)
    names = [lines_.clip_name(line["n"], largest) for line in rows]
    if args.dry_run:
        phonemize = _phonemizer(LINES_LANG) if args.phonemes else None   # before anything is printed
        print(f"narrate (dry run): {args.lines}")
        print(f"voice {voice}, speed {speed}, model kokoro-82m from {os.path.dirname(model)}")
        total = 0.0
        for line, name in zip(rows, names):
            said = line.get("say", line["text"])
            seconds = lines_.estimate(said, speed)
            total += seconds
            print(f"{name}  at {line['start']:.2f} s  ~{seconds:.1f} s  {line['text']}")
            if "say" in line:
                print(f"    say: {said}")
            if phonemize:
                print(f"    phonemes: {for_voice(said, phonemize)}")
        print(f"{len(rows)} lines, about {round(total)} s of speech; nothing written (dry run).")
        return cli.OK
    outputs = [os.path.join(folder, name) for name in names] + [timing_path]
    existing = [p for p in outputs if os.path.lexists(p)]
    if existing and not args.replace:
        raise cli.Failure("these would be written over; delete them, or run with --replace:\n"
                          + "\n".join("  " + p for p in existing))
    cli.need("numpy")
    cli.need("soundfile")
    speech = _load_model(model, voices)
    available = sorted(speech.get_voices())
    if voice not in available:
        raise cli.Failure("the model has no voice '{}' (it has {})".format(voice, ", ".join(available)))
    if existing:
        print("Replacing:\n" + "\n".join("  " + p for p in existing))
    import numpy as np
    import soundfile
    timing = {"voice": voice, "speed": speed, "model": "kokoro-82m", "sample_rate": None, "lines": []}
    os.makedirs(folder, exist_ok=True)
    spoken = []
    for i, (line, name) in enumerate(zip(rows, names)):
        try:
            to_say = for_voice(line.get("say", line["text"]), lambda text: speech.tokenizer.phonemize(text, LINES_LANG))
            samples, rate = speech.create(to_say, voice=voice, speed=speed, lang=LINES_LANG, is_phonemes=True)
        except Exception as e:  # the model's own errors are not ours to classify
            raise cli.Failure(f"the speech model failed on line {line['n']} ({e}); nothing written for it",
                              cli.EXTERNAL) from e
        samples = trim(np.asarray(samples, dtype=np.float32), rate)
        soundfile.write(os.path.join(folder, name), samples, rate)
        length = round(len(samples) / rate, 3)
        timing["sample_rate"] = rate
        timing["lines"].append({"n": line["n"], "start": line["start"], "text": line["text"], "length": length})
        with open(timing_path, "w", encoding="utf-8") as f:
            json.dump(timing, f, indent=1, ensure_ascii=False)
        print(f"{name}  {length:.3f} s", flush=True)
        spoken.append((line, length))
        warning = lines_.overrun(spoken + [(rows[i + 1], 0.0)] if i + 1 < len(rows) else spoken, i)
        if warning:
            print(f"{PROG}: {warning}", file=sys.stderr, flush=True)
    print(f"Wrote {len(rows)} clips and {timing_path}")
    return cli.OK
