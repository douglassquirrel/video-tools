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

- macOS on Apple silicon (checked on macOS 27) with [Homebrew](https://brew.sh); Linux with Python 3.10 to 3.13 for
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

### Running from the Linux device shell

Where the checkout is shared with a Linux machine (a Claude session's device shell sees it at `~/mnt/video-tools`),
the repository's `.venv` is the Mac's and cannot run there. A venv *outside* the repository, with the packages, a
settings file naming the model and three environment lines are what every session there needs; `setup-linux` does
all of it in one command and prints the lines:

```bash
eval "$(~/mnt/video-tools/setup-linux --venv /tmp/work-$(id -u)/venv --model $HOME/mnt/kokoro --conf /tmp/work-$(id -u)/video-tools.conf)"
~/mnt/video-tools/stills --help
```

It runs on the system `python3` (nothing installed), makes the venv when it is missing (`python3 -m venv
--system-site-packages DIR`), installs the packages when the venv cannot import them (`pip install numpy soundfile
"kokoro-onnx==0.6.1" Pillow`, the one step that uses the network), checks that the model folder holds `model.onnx`
and `voices.npz`, writes `SPEECH_MODEL_DIR` into the settings file and prints `export VIDEO_TOOLS_PYTHON=…`,
`export VIDEO_TOOLS_CONF=…` and `export PYTHONDONTWRITEBYTECODE=1`; a second run finds everything in place and
prints the lines alone. Every command but `cut-video` restarts itself under the Python `VIDEO_TOOLS_PYTHON` names.
Never build that venv inside the repository from Linux (it would shadow the Mac's); `setup-linux` refuses to. With
`VIDEO_TOOLS_PYTHON` unset the commands use `.venv` as above; a path that does not exist is refused with exit 3.

### One-time set-up of the speech model

Only `narrate` needs it. These are the only steps that use the network; run them once per machine. A machine that
already has the model for training-video-tools (in `~/models/kokoro/`, with `voices.npz`) needs only step 3.

1. The model and the voices, into `~/models/kokoro/`:

   ```bash
   mkdir -p ~/models/kokoro && cd ~/models/kokoro
   base=https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main
   curl -L -C - -o model.onnx "$base/onnx/model.onnx"
   for v in af_heart bm_george am_michael bf_emma; do curl -L -o "$v.bin" "$base/voices/$v.bin"; done
   ```

   (`-C -` resumes an interrupted download.) Expected: `model.onnx` 325,532,232 bytes, md5
   `0a08987b47a82ad0a67a1d92f66d95db`; each voice 522,240 bytes.

2. The single voices file kokoro-onnx wants, from the per-voice files (no network; run in `~/models/kokoro`, with
   the path to your checkout's `.venv`):

   ```bash
   ~/path/to/video-tools/.venv/bin/python -c "import numpy as np, glob, os
   v={os.path.basename(f)[:-4]: np.fromfile(f, dtype=np.float32).reshape(-1,1,256) for f in glob.glob('*.bin')}
   np.savez(open('voices.npz','wb'), **v); print(sorted(v))"
   ```

3. Tell the tools where it is, in `~/.video-tools.conf` (copy `video-tools.conf.example`):

   ```
   SPEECH_MODEL_DIR=~/models/kokoro
   ```

4. Check: `./narrate --lines TABLE.md --out clips --dry-run` names the model's folder and the voice.

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

### `compare-video NEW.mp4 OLD.mp4 [--every SECONDS] [--sheet OUT.png]`

The acceptance of a re-made or revised video: two finished files compared and reported, never judged (exit 0
whenever it runs; a remake that is meant to differ still compares). For each file, the length, frame count, peak
and mean level; then the narration envelopes (each file's audio decoded to 48 kHz mono, the RMS of every 0.1 s
window), their correlation over the shorter file (`undefined` when one is flat), and the windows that are speech
(above −40 dBFS) in one and silence in the other; then one frame from each file every `--every` seconds (default
5) and the mean absolute difference of the pair over RGB, 0 to 255: the mean, the median and the five largest with
their times. With `--sheet`, those five pairs side by side, new left, old right, each labelled under the frame
(refuses an existing file). Needs ffmpeg, ffprobe and numpy, and Pillow for the sheet.

```console
$ ./compare-video new.mp4 old.mp4 --every 2 --sheet compare.png
NEW new.mp4
  length 10.000 s, 250 frames; peak -17.9 dBFS, mean -23.3 dBFS
OLD old.mp4
  length 10.000 s, 250 frames; peak -17.9 dBFS, mean -23.3 dBFS
narration envelopes (0.1 s windows, 100 compared): correlation 1.0000; speech in one and silence in the other: 0 windows
frames every 2 s (5 pairs): mean difference 58.2, median 0.0 (0-255)
  largest: 145.6 at 8.0 s, 145.3 at 6.0 s, 0.0 at 0.0 s, 0.0 at 2.0 s, 0.0 at 4.0 s
sheet of 5 pairs written to compare.png
$ ./compare-video new.mp4 gone.mp4
compare-video: no such file: gone.mp4
```

(13 November 2026, the real ffmpeg 9.0.2 on two invented 10-second clips: the same test pattern and tone, with
`new.mp4`'s colours shifted from 6 s; the two largest differences are the two frames after the shift, and the
sheet, 1920×2850, shows them first.)

### `narrate --lines TABLE.md --out FOLDER [--speed S] [--voice V] [--replace] [--dry-run [--phonemes]]`

Speaks a **description table** with the local Kokoro speech model, for audio description, whose timed lines are
spoken fast and mixed into a video's sound. `TABLE.md` is any Markdown file holding a table with the columns `#` (a
whole number from 1, each once), `Start (s)` (seconds) and `Line` (the text, spoken as written: quotes, colons,
non-ASCII and all; `\|` for a pipe), found by header in any order; other columns, other tables and everything
outside the table are ignored. Each line goes to its own trimmed clip in `FOLDER` (made if missing), `01.wav`,
`02.wav`, … (more digits when the numbers need them), and `timing.json` there holds the voice, speed, model and
sample rate and, per line, its number, start, text and real length in seconds, rewritten after each clip. `--speed`
defaults to 1.5 (the model accepts 0.5 to 2.0) and `--voice` to `VOICE` in `~/.video-tools.conf`, else `af_heart`.
Each clip's real length is printed, and where a line's start plus its length passes the next line's start, a
warning on stderr names both (exit 0 still: the writer decides). Nothing is written over an existing clip or
`timing.json` without `--replace`, which lists them first. `--dry-run` lists each line with its start and an
estimate at 2.6 words a second times the speed, and writes nothing. Any other argument (such as a training
script, `narrate SCRIPT.md`) is refused, exit 2: that form belongs to training-video-tools.

**A `Say` column, where the written line is said wrongly.** A table may also have a `Say` column, anywhere among
the others. A row whose `Say` is filled in is spoken from it instead of from `Line`, and `Say` may hold `[[…]]`
spans of phonemes, given to the voice as they stand, the text around them phonemized as usual. A row whose `Say` is
empty, and every row of a table without the column, is spoken from `Line`. Every line is given to the voice with
`, ` in front, and a quiet first consonant (s, f, θ, ʃ, h) doubled, so the voice says it in full at speed 1.5.
`timing.json` keeps the `Line` as each line's `text`, and the dry run's estimate counts the words of what is
spoken. A `Say` whose spans are wrong (an unclosed `[[`, a stray `]]`, an empty span, a symbol the voice does not
know) is refused before the model is loaded, naming the row. To write a span, see what the voice is given:
`--dry-run --phonemes` prints each line's `Say` and its phoneme string, spans spliced in; without `--dry-run`,
`--phonemes` is refused.

```console
$ ./narrate --lines table.md --out clips --dry-run --phonemes
narrate (dry run): table.md
voice af_heart, speed 1.5, model kokoro-82m from /Users/you/models/kokoro
01.wav  at 0.10 s  ~1.8 s  A kite climbs over the harbour wall.
    phonemes: , ɐ kˈaɪt klˈaɪmz ˌoʊvɚ ðə hˈɑːɹbɚ wˈɔːl.
02.wav  at 2.00 s  ~0.5 s  Silas smiles.
    say: [[sˈaɪləs]] smiles.
    phonemes: , ssˈaɪləs smˈaɪlz.
03.wav  at 3.00 s  ~1.3 s  On screen: “Harbour”; it's dusk.
    phonemes: , ˌɔn skɹˈiːn: “hˈɑːɹbɚ”; ɪts dˈʌsk.
3 lines, about 4 s of speech; nothing written (dry run).
$ ./narrate --lines table.md --out clips
01.wav  1.245 s
02.wav  0.725 s
03.wav  1.277 s
Wrote 3 clips and clips/timing.json
$ ./narrate --lines table.md --out clips
narrate: these would be written over; delete them, or run with --replace:
  clips/01.wav
  clips/02.wav
  clips/03.wav
  clips/timing.json
```

(13 November 2026, the real model on an invented three-line table whose `Say` column follows `Line`; the home
folder shortened to `/Users/you`. The clips and `timing.json` are byte for byte those training-video-tools'
`narrate --lines` writes from the same table.)

**How fast.** kokoro-onnx 0.6.1 accepts `speed` from 0.5 to 2.0 and refuses more, so 2.0 is the fastest. Measured
in training-video-tools on an invented 15-word line in `af_heart`: 1.0 took 4.69 s (3.4 words a second), 1.5 took
2.98 s (5.4) and 2.0 took 2.62 s (6.1). A table that assumes five words a second is close to speed 1.5.

### `setup-linux --venv DIR --model DIR --conf FILE [--dry-run]`

The Linux device shell's preparation in one command ("Running from the Linux device shell" above): the venv made
or reused, the packages installed when missing, the model folder checked, the settings file written, the three
environment lines printed on stdout and nothing else there, so `eval "$(./setup-linux …)"` or a script that pastes
the lines into an `env.sh` can take them as they are. Progress (the venv made, the packages installed, the settings
written) goes to stderr, and nothing at all is said when everything was already in place. Standard library only,
on the `python3` that runs it (3.9 or later): this is the command that makes the venv the others run under, so it
cannot use it.

- `--venv DIR`: the venv, outside this checkout (inside it is refused, exit 2). Missing, it is made with the
  `python3` on PATH; present, it is reused. Then `DIR/bin/python` is asked to import the four packages, and only
  when that fails are they installed.
- `--model DIR`: must hold `model.onnx` and `voices.npz` ("One-time set-up of the speech model"). Each missing file
  is named, exit 3; the venv and the settings are still done first, so one run reports everything it can.
- `--conf FILE`: written with `SPEECH_MODEL_DIR=<the model folder>` when the file is missing or its
  `SPEECH_MODEL_DIR` is absent or different; every other line is kept, and a file that already says it is not
  touched. The folder is made if needed. A file that cannot be read as settings (a line that is not `KEY=value`, an
  unknown setting) is refused in words, exit 3, and left alone.
- `--dry-run`: the same checks, then a `Would make the venv at …`, `Would install … into …`, `Would write … with
  SPEECH_MODEL_DIR=…` line for each thing a real run would do, and the three lines; nothing is run, made or written
  but the import check (when the venv exists).
- Paths are made absolute, and those with spaces or other characters a shell would split are quoted in the lines.

```console
$ ./setup-linux --venv /tmp/work/venv --model ~/models/kokoro --conf /tmp/work/video-tools.conf --dry-run
Would make the venv at /tmp/work/venv
Would install numpy soundfile kokoro-onnx==0.6.1 Pillow into /tmp/work/venv
Would write /tmp/work/video-tools.conf with SPEECH_MODEL_DIR=/Users/you/models/kokoro
export VIDEO_TOOLS_PYTHON=/tmp/work/venv/bin/python
export VIDEO_TOOLS_CONF=/tmp/work/video-tools.conf
export PYTHONDONTWRITEBYTECODE=1
$ ./setup-linux --venv ./linux-venv --model ~/models/kokoro --conf /tmp/work/c.conf
setup-linux: --venv ./linux-venv is inside this checkout (/Users/you/video-tools); the Linux venv must be made outside it, or it would shadow the Mac's .venv (README, "Running from the Linux device shell")
```

(13 November 2026, on the Mac's own Python 3.9.6; the work folder and home folder shortened. With the model folder
missing the same dry run says, on stderr, `setup-linux: the model folder … does not exist; download the model into
it as the README's "One-time set-up of the speech model" says` and exits 3. A `venv` or `pip` run that fails is
reported with its last five lines and exit 3; the venv is kept after a failed install, so the next run installs
again.)

### Settings: `~/.video-tools.conf`

`KEY=value` lines, `#` comments, optional quotes, `~` for your home folder in a folder's path; read, never run.
`VIDEO_TOOLS_CONF` in the environment names another file. Only `narrate` and `setup-linux` read it; a line that is
not `KEY=value`, or any other key, is refused naming the line.

| Key | Meaning |
|---|---|
| `SPEECH_MODEL_DIR` | The folder holding `model.onnx` and `voices.npz`. Required by `narrate`. |
| `VOICE` | `narrate --lines`' voice when `--voice` is not given (else `af_heart`). |

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
| 2 | Bad arguments (see `--help`). For `setup-linux`: a `--venv` inside this checkout. For `narrate`: no `--lines`, no `--out`, an argument that is not a flag (a training script), a speed outside 0.5 to 2.0, `--phonemes` without `--dry-run`. For `stills`: a first argument ending `.md` (a training script), no choice of `--at`, `--every` or `--changes`, or two; `--threshold` without `--changes` or outside 0 to 1; `--detect-fps` of 0 or less or without `--changes`; `--every` of 0 or less; a time at or past the video's end (the length is given); `--from` or `--until` with `--at`, with `--sheet` alone or not a time; `--from` at or past the end; `--until` not after `--from`; a `--grid` that is not two whole numbers of at least 1. | Fix the command line. |
| 3 | An input refuses, and nothing is written. For `stills`: any still, `stills.txt` or sheet it would write already exists (with `--from` or `--until`, `stills.txt` is added to instead, and a still not in it is written over); for `--sheet` alone, `stills.txt` or a still it names is missing, it lists no stills, a line of it is not `TIME NAME`, or the video is missing. For `compare-video`: either file is missing, or the sheet exists. For `narrate`: the table is missing, has no `#`, `Start (s)` and `Line` columns or a row that cannot be spoken (named), or a `Say` whose spans are wrong (the row and the problem named); `SPEECH_MODEL_DIR` is not set or has no model; the voice is not in the voices file; a clip or `timing.json` exists without `--replace`. A settings file that cannot be read (the line named). `VIDEO_TOOLS_PYTHON` names no such file. For `setup-linux`: the model folder or one of its two files is missing (named), the settings file cannot be read as one, no `python3` is on PATH to make the venv, or the `venv` or `pip install` step failed (its last lines shown; the venv is kept); what it did before the step that failed stays. | Fix the input, or move the output away. |
| 4 | A package (numpy, soundfile, Pillow, kokoro-onnx) is not installed in the Python running the command: one line names it, its `pip install` line and, when `VIDEO_TOOLS_PYTHON` is unset, the device-shell set-up; ffmpeg or ffprobe is not on PATH; ffmpeg failed (its output is shown); the speech model failed on a line (named). What was written before stays. | Install as above, or read ffmpeg's message. |

## Testing

```bash
/opt/homebrew/bin/python3.12 -m venv .venv                                   # once
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt            # once
.venv/bin/pytest            # the whole suite, with coverage (about a minute)
.venv/bin/ruff check .      # lint
```

The suite needs no ffmpeg, no speech model and no network. `tests/tier1/` tests the pure parts (reading and writing
`.srt`, finding phrases, where a cut falls, the description table, phoneme spans, the stills' times and names, the
compare measures, the settings file). `tests/tier2/` runs each command against stand-ins: for `cut-video`, `ffmpeg`
and `ffprobe` from `tests/stubs/ffstub.py`, which record their arguments and fail on demand; for the others, an
`ffmpeg` and `ffprobe` that read fake media files (`tests/stubs/fakemedia.py`), a fake speech model
(`tests/stubs/kokoro_onnx/`) and a fake `python3` for `setup-linux` (`tests/stubs/pystub.py`), all put on `PATH` or
`PYTHONPATH` by `tests/tier2/conftest.py`. Every refusal and exit code, `--help`, `--dry-run`, no partial file after
a failure, and the inputs unchanged byte for byte are tested there. The commands under test run from an empty
temporary folder, so even a fault cannot write into the checkout. Run one tier with `.venv/bin/pytest tests/tier1`.
Coverage: 99% of `videotools/` (13 November 2026, 277 tests); the one line not measured is `setup-linux`'s refusal
of a venv inside the checkout, which is tested on a copy of the checkout that coverage does not follow.

The tests of `stills`, `compare-video`, `narrate --lines` and `setup-linux` came from training-video-tools with
their code. Each was shown to fail when the code it guards was broken on purpose, and tests were added for what no
test there pinned.

**Manual checks with the real programs** (not automated), recorded 13 November 2026 with ffmpeg 9.0.2 and the
Kokoro model on invented clips and an invented table, in a scratch folder: the examples in "Usage" are those runs.
`stills`, `compare-video` and `narrate --lines` each wrote, byte for byte, what training-video-tools' own command
writes from the same inputs; `setup-linux --dry-run` was run on the Mac's own Python 3.9.6. For `cut-video`: make a
short clip and an invented transcript, then run `--help`, `--dry-run` and a real cut, and check the result with
`ffprobe -v error -show_entries format=duration:stream=codec_type -of compact out/clip-cut.mp4`. Done on 3 November
2026 on a 10-second test clip: the 7-second cut came out at 7.000000 s with one video and one audio stream, and a
second run into the same folder refused with exit 9.

## Known limitations and non-goals

- It never chooses what to cut: you give it the phrases.
- It cuts at caption boundaries, not at the exact word; whisper-style captions are short enough for that.
- It only cuts the beginning and the end: nothing out of the middle, no joining.
- It re-encodes, so a cut takes time and is not bit-for-bit the original's quality settings.
- `stills --changes` finds what ffmpeg's scene detection scores as a change; a cut it scores low (such as between two
  flat colours of similar brightness) is missed. Lower `--threshold`, or use `--every`.
- `compare-video` reports and never judges: whether a difference matters is yours to say.
- `narrate` speaks English (`en-us`) only, with the Kokoro-82M model's voices; it never mixes the clips into a video.
- The forms of `stills` and `narrate` that take a training script are training-video-tools', and are refused here.
- Two commands write over their own earlier output, and only these two: `narrate --lines --replace`, when asked, and
  `stills` with `--from` or `--until`, which adds to `stills.txt` and writes again over a still a cut-off run left
  unlisted. Nothing ever writes over an input.

## Notes for users

- 3 November 2026: `cut-video` is new.
- 13 November 2026: `stills`, `compare-video`, `narrate --lines` and `setup-linux` are here, moved from
  training-video-tools with the same forms, flags, files, messages and exit codes. What changes for you:
  - Install the packages: `brew install python@3.12`, then in the checkout `/opt/homebrew/bin/python3.12 -m venv .venv`
    and `.venv/bin/pip install -r requirements.txt` ("Installation").
  - Settings: `~/.video-tools.conf` (or the file `VIDEO_TOOLS_CONF` names), with `SPEECH_MODEL_DIR` and `VOICE`
    only; any other setting is refused. training-video-tools' `~/.training-video-tools.conf` is not read: copy its
    `SPEECH_MODEL_DIR` line across.
  - In the Linux device shell, `VIDEO_TOOLS_PYTHON` and `VIDEO_TOOLS_CONF` (not `TRAINING_VIDEO_TOOLS_…`), which
    `setup-linux` prints; it installs four packages (numpy, soundfile, kokoro-onnx, Pillow).
  - `stills SCRIPT.md …` and `narrate SCRIPT.md` are refused (exit 2): run them from training-video-tools.

## Contributing

Dev tooling (pytest, pytest-cov, ruff) goes in the same gitignored `.venv/`, from `requirements-dev.txt`. Every
change starts with a failing test.
