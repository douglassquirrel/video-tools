# video-tools

Small command-line tools for working with video of any kind, run from Terminal on a Mac (and from a Linux
shell that shares the checkout). Each command takes the files it works on as arguments, only ever reads them, and
writes new files into a folder you name. For anyone describing, checking or trimming a video:

- `cut-video` cuts the beginning and end off a recording at phrases found in its SubRip (`.srt`) transcript, and
  cuts the transcript to match.
- `stills` writes frames of a video as PNGs, at given times, every so many seconds or wherever the picture
  changes, with labelled contact sheets: for seeing what is on screen when.
- `compare-video` compares two finished videos (length, frames, sound levels, narration, pictures) and reports.
- `narrate --lines` speaks each line of a table of timed description lines with a local speech model, one clip per
  line, with their lengths.
- `setup-linux` prepares a Linux shell to run them.

`stills`, `compare-video`, `narrate --lines` and `setup-linux` came from
[training-video-tools](https://github.com/douglassquirrel/training-video-tools) on 13 November 2026, unchanged
but for the names of their settings (see "Notes for users").

## Requirements

- macOS on Apple silicon (checked on macOS 26) with [Homebrew](https://brew.sh); Linux with Python 3.10 to 3.13 for
  the Linux shell (see "Running from the Linux device shell").
- `ffmpeg` and `ffprobe`: `brew install ffmpeg` installs both.
- `cut-video` needs nothing more: it runs on the Mac's own `/usr/bin/python3` (3.9 or later), standard library only.
- `stills`, `compare-video` and `narrate` need Homebrew's `python@3.12` (the speech package needs Python 3.10 to
  3.13) with the packages in `requirements.txt` (numpy, soundfile, kokoro-onnx 0.6.1, Pillow), in a `.venv` inside
  the checkout (Installation).
- `narrate` also needs the Kokoro-82M speech model, about 327 MB, in `~/models/kokoro/`, and `~/.video-tools.conf`
  naming its folder ("One-time set-up of the speech model").

## Installation

Paste into Terminal, from the folder you keep code in:

```bash
brew install ffmpeg python@3.12
git clone https://github.com/douglassquirrel/video-tools.git
cd video-tools
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
./stills --help
```

Run the commands from the checkout, or give their full path from anywhere; they work from any folder. `stills`,
`compare-video` and `narrate` find the `.venv` themselves, whichever `python3` your shell has; `cut-video` needs no
`.venv`. Nothing is installed or copied outside the folder.

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

### `cut-video [--dry-run] [--from PHRASE] [--to PHRASE] --out DIR VIDEO TRANSCRIPT`

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

`cut-video` reads no configuration file: everything is on the command line. Its exit codes are its own (below).

### `stills VIDEO (--at T[,T…] | --every SECONDS [--from T] [--until T] | --changes [--threshold N] [--detect-fps N] [--from T] [--until T]) --out FOLDER [--sheet SHEET.png] [--grid CxR]`
### `stills VIDEO --sheet SHEET.png --out FOLDER [--grid CxR]`

For seeing what is on screen when: one PNG per frame at the video's own size, written into `--out FOLDER` (made
if missing) and named by its time so the names sort in order (`t0012.40.png`), plus `stills.txt` listing each time
and file name, one to a line. Choose the frames one way: `--at 0,1.5,3` for the times given, in seconds;
`--every 2` for every two seconds from 0 while less than the video's length; `--changes` for the first frame and
every frame where the picture changes, by ffmpeg's scene detection (`--threshold`, 0 to 1, default 0.3, is the score
a change must beat; lower finds more). With `--sheet`, also a contact sheet: each frame in a cell 360 px wide and
as tall as the video's proportions need, so a vertical Short and a landscape video each keep their shape, with its
time in a grey strip under the frame, never over it; `--grid CxR` sets the cells per sheet (default: the smallest
square that holds them, at most five across), and more frames than a grid holds go on numbered sheets,
`SHEET-1.png`, `SHEET-2.png`, …. Refuses, before anything is read, an existing still, listing or sheet, no choice
or two, a bad `--grid`, `--threshold` without `--changes`, `--every` of 0 or less, and a time at or past the end
(saying the length). Needs ffmpeg, ffprobe and Pillow. `stills.txt` is written a line at a time, as each still is
written, so a run that is killed part-way leaves a listing of exactly the stills there. Each still is written to a
part name (`.t0012.40.png.part`), listed, and only then renamed, so a still with its name is always listed; a kill
leaves at worst a part file. A first argument ending `.md` is refused (exit 2): the forms of `stills` that take a
training script belong to training-video-tools.

**A long video in slices** (for a shell that cuts a call off, such as the Linux device shell's three minutes):
`--from T` and `--until T`, in seconds, with `--every` or `--changes`, take only the window from `--from` (default
0) up to but not including `--until` (default the end; past the end is the end, so slices at round numbers need
not know the length). The scan seeks to the window, so a slice costs its own length. Slices go into the same
`--out` folder: with a window an existing `stills.txt` is added to, not refused, and a still the listing names is
refused as always; a still that is there but not listed, or a part file, is a killed run's leftover and is written
over (the unlisted still is said on stderr, `t0807.80.png was there but not listed; written again`; the part file
silently). Without a window, any existing still is refused. `--changes` lists the video's first frame only when the
window starts at 0, and `--every` steps from `--from`, so slices joined give exactly what one whole run gives. With
no `--at`, `--every` or `--changes`, `--sheet SHEET.png --out FOLDER` draws the sheet of every still
`FOLDER/stills.txt` lists, in that order, reading nothing from the video (the file must still exist): the last call
after the slices. `--from` at or past the end, `--until` not after `--from`, a window with `--at`, or a window with
`--sheet` alone are refused (exit 2); a missing or empty listing, a missing still, or a listing line that is not
`TIME NAME`, exit 3.

**How `--changes` scores**: ffmpeg scores the picture 10 times a second, not every frame (`fps=10` before the
`select` filter), so a cut is reported at the first scored moment after it, within a tenth of a second, and the
still is read there; `--detect-fps N` changes the rate (above 0; fewer is a little faster, more is finer). The
audio track is not decoded. `--changes` runs ffmpeg once over the file or the window
(`fps=10,select='gt(scene,N)',metadata=print`) and then reads each chosen frame; a frame ffmpeg cannot read is an
error (exit 4) and the stills written before it stay, listed.

```console
$ ./stills cuts.mp4 --changes --out cuts-stills --sheet cuts.png
t0000.00.png at 0.000 s
t0004.00.png at 4.000 s
Wrote 2 stills to cuts-stills and the sheet cuts.png
$ cat cuts-stills/stills.txt
0.00 t0000.00.png
4.00 t0004.00.png
$ ./stills cuts.mp4 --at 1,9 --out late
stills: 9 s is past the end of cuts.mp4 (5.520 s)
$ ./stills cuts.mp4 --changes --until 3 --out sliced
t0000.00.png at 0.000 s
Wrote 1 still to sliced
$ ./stills cuts.mp4 --changes --from 3 --out sliced
t0004.00.png at 4.000 s
Wrote 1 still to sliced
$ ./stills cuts.mp4 --sheet sliced/sheet.png --out sliced
Drew 2 stills from sliced/stills.txt on the sheet sliced/sheet.png
```

(13 November 2026, the real ffmpeg 9.0.2: `cuts.mp4` is an invented 160×90 clip, red, then green from 2 s, then
blue from 4 s, 5.52 s long; the sheet is 720×239. ffmpeg's scene score finds the cut to blue but not the one from
red to green, even at `--threshold 0.1`: what counts as a change is ffmpeg's to say. The two slices give the same
stills, byte for byte, as the whole run.)

## Errors and exit codes

Every refusal is a line on stderr starting with the command's name, saying what is wrong and what to do; never a
traceback. `cut-video` has its own codes; the other commands share theirs (the second table).

### `cut-video`

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

### `stills`, `compare-video`, `narrate`, `setup-linux`

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Success; with `--dry-run`, everything checked and nothing written. `compare-video` reports and never judges: 0 whenever it runs. | |
| 2 | Bad arguments (see `--help`). For `stills`: a first argument ending `.md` (a training script), no choice of `--at`, `--every` or `--changes`, or two; `--threshold` without `--changes` or outside 0 to 1; `--detect-fps` of 0 or less or without `--changes`; `--every` of 0 or less; a time at or past the video's end (the length is given); `--from` or `--until` with `--at`, with `--sheet` alone or not a time; `--from` at or past the end; `--until` not after `--from`; a `--grid` that is not two whole numbers of at least 1. | Fix the command line. |
| 3 | An input refuses, and nothing is written. For `stills`: any still, `stills.txt` or sheet it would write already exists (with `--from` or `--until`, `stills.txt` is added to instead, and a still not in it is written over); for `--sheet` alone, `stills.txt` or a still it names is missing, it lists no stills, a line of it is not `TIME NAME`, or the video is missing. A settings file that cannot be read (the line named). `VIDEO_TOOLS_PYTHON` names no such file. | Fix the input, or move the output away. |
| 4 | A package (numpy, soundfile, Pillow, kokoro-onnx) is not installed in the Python running the command: one line names it, its `pip install` line and, when `VIDEO_TOOLS_PYTHON` is unset, the device-shell set-up; ffmpeg or ffprobe is not on PATH; ffmpeg failed (its output is shown). What was written before stays. | Install as above, or read ffmpeg's message. |

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
