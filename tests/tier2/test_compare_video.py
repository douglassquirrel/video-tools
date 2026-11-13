"""compare-video (taken in from training-video-tools at fc6091a): two finished files on length, frames, levels, envelopes and pictures; the stub
supplies the media (fake files whose `tone` spans are loud and whose `colours` change at times)."""

import os

import pytest
from PIL import Image

from tests.tier2.conftest import fake_media, ff_calls, run

FRAMES = 1587
DURATION = f"{FRAMES / 30:.6f}"      # 52.900000: 529 windows of 0.1 s


def media(tmp_path, name, **fields):
    defaults = {"frames": FRAMES, "duration": DURATION, "max_volume": "-1.0", "mean_volume": "-20.0",
                "tone": "0-47.2", "colours": "0:200.40.40"}
    defaults.update(fields)
    return fake_media(str(tmp_path / name), **defaults)


@pytest.fixture
def pair(tmp_path, ffstub):
    return media(tmp_path, "new.mp4"), media(tmp_path, "old.mp4")


def test_help_and_usage():
    code, out, err = run("compare-video", "--help")
    assert code == 0 and out.startswith("usage: compare-video [-h] [--every SECONDS] [--sheet OUT.png] NEW OLD")
    code, out, err = run("compare-video", "x.mp4")
    assert code == 2 and "usage: compare-video" in err


def test_a_file_against_itself_reports_every_measure_and_no_difference(pair, ffstub):
    new, old = pair
    code, out, err = run("compare-video", new, new, env=ffstub)
    assert (code, err) == (0, "")
    assert out == (f"NEW {new}\n"
                   "  length 52.900 s, 1587 frames; peak -1.0 dBFS, mean -20.0 dBFS\n"
                   f"OLD {new}\n"
                   "  length 52.900 s, 1587 frames; peak -1.0 dBFS, mean -20.0 dBFS\n"
                   "narration envelopes (0.1 s windows, 529 compared): correlation 1.0000; "
                   "speech in one and silence in the other: 0 windows\n"
                   "frames every 5 s (11 pairs): mean difference 0.0, median 0.0 (0-255)\n"
                   "  largest: 0.0 at 0.0 s, 0.0 at 5.0 s, 0.0 at 10.0 s, 0.0 at 15.0 s, 0.0 at 20.0 s\n")
    assert sorted(os.listdir(os.path.dirname(new))) == ["bin", "ff-calls.jsonl", "new.mp4", "old.mp4"]


def test_the_audio_is_decoded_to_48_khz_mono_16_bit_and_frames_read_raw_at_each_time(pair, ffstub):
    new, old = pair
    assert run("compare-video", new, old, "--every", "20", env=ffstub)[0] == 0
    calls = ff_calls(ffstub)
    audio = [c["ffmpeg"] for c in calls if "ffmpeg" in c and "s16le" in c["ffmpeg"]]
    assert audio == [["-hide_banner", "-loglevel", "error", "-nostdin", "-i", p, "-map", "0:a", "-f", "s16le",
                      "-ac", "1", "-ar", "48000", "-"] for p in (new, old)]
    frames = [c["ffmpeg"] for c in calls if "ffmpeg" in c and "-frames:v" in c["ffmpeg"]]
    assert frames[0] == ["-hide_banner", "-loglevel", "error", "-nostdin", "-ss", "0.000", "-i", new, "-frames:v", "1",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-"]
    assert [(c[5], c[7]) for c in frames] == [(t, p) for t in ("0.000", "20.000", "40.000") for p in (new, old)]


def test_the_five_largest_frame_differences_come_first_with_their_times(pair, tmp_path, ffstub):
    new, _ = pair
    old = media(tmp_path, "old2.mp4", colours="0:200.40.40,10:0.0.255,25:255.255.255,40:200.40.40")
    code, out, err = run("compare-video", new, old, env=ffstub)
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[5] == "frames every 5 s (11 pairs): mean difference 85.5, median 151.7 (0-255)"
    assert lines[6] == "  largest: 161.7 at 25.0 s, 161.7 at 30.0 s, 161.7 at 35.0 s, 151.7 at 10.0 s, 151.7 at 15.0 s"


def test_different_lengths_are_both_reported_and_compared_over_the_shorter(pair, tmp_path, ffstub):
    new = media(tmp_path, "long.mp4", tone="0-10,15-47.2")
    old = media(tmp_path, "short.mp4", frames=600, duration="20.000000", tone="0-10,15-20")   # the same for 20 s
    code, out, err = run("compare-video", new, old, env=ffstub)
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[1] == "  length 52.900 s, 1587 frames; peak -1.0 dBFS, mean -20.0 dBFS"
    assert lines[3] == "  length 20.000 s, 600 frames; peak -1.0 dBFS, mean -20.0 dBFS"
    assert lines[4].startswith("narration envelopes (0.1 s windows, 200 compared): correlation 1.0000;")
    assert lines[5] == "frames every 5 s (4 pairs): mean difference 0.0, median 0.0 (0-255)"
    assert lines[6] == "  largest: 0.0 at 0.0 s, 0.0 at 5.0 s, 0.0 at 10.0 s, 0.0 at 15.0 s"


def test_speech_in_one_and_silence_in_the_other_is_counted_and_lowers_the_correlation(pair, tmp_path, ffstub):
    new = media(tmp_path, "n2.mp4", tone="0-10,20-30")
    old = media(tmp_path, "o2.mp4", tone="0-10,25-30")
    code, out, err = run("compare-video", new, old, env=ffstub)
    assert (code, err) == (0, "")
    assert out.splitlines()[4] == ("narration envelopes (0.1 s windows, 529 compared): correlation 0.8069; "
                                   "speech in one and silence in the other: 50 windows")


def test_a_flat_envelope_has_no_correlation(pair, tmp_path, ffstub):
    new = media(tmp_path, "n3.mp4", tone="0-52.9")
    code, out, err = run("compare-video", new, new, env=ffstub)
    assert (code, err) == (0, "")
    assert out.splitlines()[4] == ("narration envelopes (0.1 s windows, 529 compared): correlation undefined "
                                   "(a flat envelope); speech in one and silence in the other: 0 windows")


def test_the_sheet_shows_the_five_largest_pairs_new_left_old_right_labelled_under_each(pair, tmp_path, ffstub):
    new, _ = pair
    old = media(tmp_path, "old2.mp4", colours="0:200.40.40,10:0.0.255,25:255.255.255,40:200.40.40")
    sheet = str(tmp_path / "sheet.png")
    code, out, err = run("compare-video", new, old, "--sheet", sheet, env=ffstub)
    assert (code, err) == (0, "")
    assert out.splitlines()[-1] == f"sheet of 5 pairs written to {sheet}"
    im = Image.open(sheet).convert("RGB")
    assert im.size == (1920, 5 * (534 + 36))         # two 950-wide frames a row, a 36 px strip under each
    assert im.getpixel((100, 100)) == (200, 40, 40)   # new, at 25 s
    assert im.getpixel((1100, 100)) == (255, 255, 255)   # old, at 25 s
    assert im.getpixel((1100, 3 * 570 + 100)) == (0, 0, 255)   # old, at 10 s (fourth row)
    assert im.getpixel((600, 534 + 18)) == (0x55, 0x55, 0x55)  # the strip under the first new frame, past its label


def test_an_existing_sheet_is_refused_before_anything_runs(pair, tmp_path, ffstub):
    new, old = pair
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"keep")
    code, out, err = run("compare-video", new, old, "--sheet", str(sheet), env=ffstub)
    assert (code, out) == (3, "")
    assert err == f"compare-video: {sheet} already exists; give a new name\n"
    assert sheet.read_bytes() == b"keep" and ff_calls(ffstub) == []


def test_a_missing_file_is_refused_by_name(pair, tmp_path, ffstub):
    new, _ = pair
    code, out, err = run("compare-video", new, str(tmp_path / "none.mp4"), env=ffstub)
    assert (code, out) == (3, "")
    assert err == f"compare-video: no such file: {tmp_path / 'none.mp4'}\n"


def test_every_must_be_positive(pair, ffstub):
    new, old = pair
    code, out, err = run("compare-video", new, old, "--every", "0", env=ffstub)
    assert code == 2 and "--every must be more than 0" in err


def test_ffmpeg_failing_on_a_frame_is_reported_exit_4(pair, ffstub):
    new, old = pair
    code, out, err = run("compare-video", new, old, env=dict(ffstub, FFSTUB_FAIL="frame"))
    assert code == 4
    assert err.startswith(f"compare-video: ffmpeg failed (exit 1) reading the frame of {new} at 0.000 s; its output follows\n")


def test_the_inputs_are_never_modified(pair, ffstub):
    new, old = pair
    before = open(new, "rb").read(), open(old, "rb").read()
    assert run("compare-video", new, old, env=ffstub)[0] == 0
    assert (open(new, "rb").read(), open(old, "rb").read()) == before


def test_a_file_that_does_not_state_its_frame_count_has_its_frames_counted(pair, tmp_path, ffstub):
    new, _ = pair
    old = media(tmp_path, "unstated.mp4", unstated_frames="1")
    code, out, err = run("compare-video", new, old, "--every", "50", env=ffstub)
    assert (code, err) == (0, "")
    assert out.splitlines()[3] == "  length 52.900 s, 1587 frames; peak -1.0 dBFS, mean -20.0 dBFS"
    probes = [c["ffprobe"] for c in ff_calls(ffstub) if "ffprobe" in c]
    assert [p for p in probes if "-count_frames" in p] == [
        ["-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
         "-of", "json", old]]


def test_frames_are_read_at_the_new_videos_own_size(tmp_path, ffstub):
    new = media(tmp_path, "tall.mp4", width="480", height="854")
    old = media(tmp_path, "tall-old.mp4", width="480", height="854")
    code, out, err = run("compare-video", new, old, "--every", "50", env=ffstub)
    assert (code, err) == (0, "")
    frames = [c["ffmpeg"] for c in ff_calls(ffstub) if "ffmpeg" in c and "-frames:v" in c["ffmpeg"]]
    assert {f[f.index("-s") + 1] for f in frames} == {"480x854"}


def test_the_levels_are_the_last_report_ffmpeg_gives(tmp_path, ffstub):
    new = media(tmp_path, "n.mp4", early_report="1", max_volume="-3.5", mean_volume="-18.25")
    code, out, err = run("compare-video", new, new, "--every", "50", env=ffstub)
    assert (code, err) == (0, "")
    assert out.splitlines()[1] == "  length 52.900 s, 1587 frames; peak -3.5 dBFS, mean -18.2 dBFS"


def test_ffmpeg_failing_or_giving_no_levels_is_reported_exit_4(tmp_path, ffstub):
    new = media(tmp_path, "n.mp4")
    code, out, err = run("compare-video", new, new, env=dict(ffstub, FFSTUB_FAIL="volume"))
    assert (code, out) == (4, "")
    assert err.startswith(f"compare-video: ffmpeg failed (exit 1) measuring the levels of {new}; its output follows\n")
    quiet = media(tmp_path, "q.mp4", no_levels="1")
    code, out, err = run("compare-video", quiet, quiet, env=ffstub)
    assert (code, out) == (4, "")
    assert err.startswith(f"compare-video: ffmpeg's volumedetect gave no levels for {quiet}; its output follows\n")
