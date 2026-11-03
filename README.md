# video-tools

Small command-line tools for working with video of any kind, run from Terminal on a Mac. Each command takes the
files it works on as arguments, only ever reads them, and writes new files into a folder you name. There is one
command so far, `cut-video`, which cuts the beginning and end off a recording at phrases found in its transcript
and cuts the transcript to match. It is for anyone who has a recording and a SubRip (`.srt`) transcript of it,
such as the one a speech-to-text tool writes, and wants to trim the chatter before and after the part that matters.

## Requirements

- macOS with its own Python 3 (`/usr/bin/python3`, 3.9 or later); nothing beyond Python's standard library. It also
  runs under Linux with Python 3.9 or later.
- `ffmpeg` and `ffprobe`, from [Homebrew](https://brew.sh): `brew install ffmpeg` installs both.

## Installation

```bash
brew install ffmpeg
git clone https://github.com/douglassquirrel/video-tools.git
cd video-tools
./cut-video --help
```

Run the commands from the checkout, or give their full path from anywhere; they work from any folder. Nothing is
installed or copied elsewhere.

## Quick start

Look first, with `--dry-run`, which reads everything, makes every check and says what it would do, writing nothing:

```console
$ ./cut-video --dry-run --from "welcome to" --to "thank you" --out out clip.mp4 clip.srt
Start: 00:00:02.000, the start of cue 2 (--from "welcome to")
      1  00:00:00.000 --> 00:00:02.000  Is this on?
  >   2  00:00:02.000 --> 00:00:04.500  Welcome to the show.
      3  00:00:04.500 --> 00:00:07.000  Today, cutting video.
End: 00:00:09.000, the end of cue 4 (--to "thank you")
      3  00:00:04.500 --> 00:00:07.000  Today, cutting video.
  >   4  00:00:07.000 --> 00:00:09.000  That's all, thank you.
      5  00:00:09.000 --> 00:00:10.000  Is it off?
Length: 00:00:07.000 of the video's 00:00:10.000, 3 cues.
Would write out/clip-cut.mp4, clip-cut.srt and clip-cut.txt.
ffmpeg command (the video is written under a temporary name, renamed when complete):
  ffmpeg -nostdin -hide_banner -loglevel error -y -ss 2.000 -i /…/clip.mp4 -t 7.000 -map 0:v:0 -map '0:a:0?' -c:v libx264 -c:a aac -movflags +faststart -f mp4 /…/out/clip-cut.mp4
Dry run: nothing written.
```

(The ffmpeg command shows full paths; they are shortened to `/…/` here.) Then cut:

```console
$ ./cut-video --from "welcome to" --to "thank you" --out out clip.mp4 clip.srt
Cut 00:00:02.000 to 00:00:09.000 (00:00:07.000 long), 3 cues.
Wrote out/clip-cut.mp4
Wrote out/clip-cut.srt
Wrote out/clip-cut.txt
```

## Usage

```
cut-video [--dry-run] [--from PHRASE] [--to PHRASE] --out DIR VIDEO TRANSCRIPT
```

- `--from PHRASE`: the cut starts at the start of the caption (cue) where this phrase begins. Without it, the video
  keeps its beginning.
- `--to PHRASE`: the cut ends at the end of the caption where this phrase ends. Without it, the video keeps its end.
  Give `--from`, `--to` or both.
- `--out DIR`: the folder to write into. It is made if missing. Nothing already in it is ever written over.
- `--dry-run`: say where the cut falls, with the caption before and after each cut, how long the result will be, and
  the ffmpeg command it would run; write nothing and make no folder.
- `VIDEO`: the recording, in any format ffmpeg reads. Only read.
- `TRANSCRIPT`: its SubRip (`.srt`) transcript, UTF-8. Only read.

**How a phrase is found.** Case, punctuation and runs of white space are ignored, and accented letters match
however they are encoded (NFC or NFD). Apostrophes are dropped, so `don't`, `don’t` and `dont` are the same word;
any other punctuation separates words. A phrase matches whole words only (`and so` does not match "and soon"), and
may run across two or more captions. It must be found exactly once: if it is found more than once, the command
says where, so you can give a longer phrase.

**What it writes**, into `DIR`, where `STEM` is the video's file name without its extension:

- `STEM-cut.mp4`: the video from the start to the end of the cut, re-encoded (H.264 video, AAC audio) so the cut is
  exact to the frame, not at the nearest keyframe. Only the first video stream and the first audio stream are kept;
  any other streams (data, subtitles, a second audio track) are left out. A video with no audio is cut without.
- `STEM-cut.srt`: the captions from the one where the cut starts to the one where it ends, their times moved back
  by the start of the cut (and kept within it), numbered from 1.
- `STEM-cut.txt`: the same captions as plain text, one caption per line, without times.

All three are written under temporary names in `DIR` and renamed only when all three are complete, so a run that
fails or is stopped with Ctrl-C leaves nothing behind. Encoding takes as long as the cut is long; there is no time
limit.

There is no configuration file: everything is on the command line.

## Errors and exit codes

Every refusal is one line on stderr starting `cut-video:`, saying what is wrong and what to do.

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Done (or the dry run said what it would do) | |
| 2 | Bad arguments: neither `--from` nor `--to`, a phrase with no words, a missing `--out` | Fix the command line; see `--help` |
| 3 | The video or transcript is missing or unreadable, or the transcript is not UTF-8 | Check the path; save the transcript as UTF-8 |
| 4 | The transcript is not a SubRip file it can read (the message names the line), or holds no captions | Fix that line of the transcript |
| 5 | A phrase is not in the transcript | Check the phrase against the transcript |
| 6 | A phrase is found more than once (the message gives the time of each) | Give a longer phrase, found only once |
| 7 | The end is not after the start, or the start is after the video ends | Check which phrase is which |
| 8 | `ffmpeg` or `ffprobe` is not installed | `brew install ffmpeg` |
| 9 | `DIR` already holds a file the run would write, is a file, or cannot be made | Move the file, or give another `--out` |
| 10 | `ffprobe` cannot read the video, or gives no duration | Check the file is a video ffmpeg can read |
| 11 | `ffmpeg` failed; its message is shown, and nothing was written | Read ffmpeg's message |
| 130 | Stopped with Ctrl-C; nothing was written | |

## Testing

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # once
.venv/bin/pytest            # the whole suite, with coverage
.venv/bin/ruff check .      # lint
```

The suite needs neither ffmpeg nor a network. `tests/tier1/` tests the pure parts (reading and writing `.srt`,
finding phrases, where the cut falls, the ffmpeg arguments). `tests/tier2/` runs the command against stand-ins for
`ffmpeg` and `ffprobe` (`tests/stubs/ffstub.py`, put on `PATH` by `tests/tier2/conftest.py`) that record their
arguments and fail on demand: every refusal and exit code, `--help`, `--dry-run`, no partial file after a failure,
and the inputs unchanged byte for byte. Run one tier with `.venv/bin/pytest tests/tier1`. Coverage: 100% of
`videotools/` (3 November 2026, 56 tests).

**Manual check with the real ffmpeg** (not automated): make a short clip and an invented transcript in a scratch
folder, then run `--help`, `--dry-run` and a real cut, and check the result with
`ffprobe -v error -show_entries format=duration:stream=codec_type -of compact out/clip-cut.mp4`. Done on
3 November 2026 with ffmpeg 9.0.2 on a 10-second test clip: the 7-second cut came out at 7.000000 s with one video
and one audio stream, and a second run into the same folder refused with exit 9.

## Known limitations and non-goals

- It never chooses what to cut: you give it the phrases.
- It cuts at caption boundaries, not at the exact word; whisper-style captions are short enough for that.
- It only cuts the beginning and the end: nothing out of the middle, no joining.
- It re-encodes, so a cut takes time and is not bit-for-bit the original's quality settings.

## Notes for users

- 3 November 2026: `cut-video` is new.

## Contributing

Dev tooling (pytest, pytest-cov, ruff) goes in a gitignored `.venv/` from `requirements-dev.txt`. Every change
starts with a failing test.
