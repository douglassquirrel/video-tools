"""stills on a video file (training-video-tools' item 24, taken in at fc6091a): frames at given times, every so many seconds or where the
picture changes, one PNG each at the video's own size plus stills.txt, and with --sheet a
labelled contact sheet; every refusal. ffmpeg and ffprobe are the stubs."""

import os

import pytest
from PIL import Image

from tests.tier2.conftest import fake_media, ff_calls, run, run_program
from videotools import sheet


@pytest.fixture
def short(tmp_path):
    """A fake vertical Short, 480x854, 8.342 s: a colour per span, as the stub serves frames."""
    return fake_media(str(tmp_path / "clip" / "video.mp4"), duration="8.342", frames="250", width="480",
                      height="854", colours="0:10.20.30,2:40.50.60,4.04:70.80.90", scenes="2,4.04")


def test_help_names_the_video_form_only():
    code, out, _err = run("stills", "--help")
    assert code == 0 and " ".join(out.split()).startswith(
        "usage: stills [-h] --out FOLDER [--grid CxR] [--at T,T,...] "
        "[--every SECONDS] [--changes] [--threshold N] [--detect-fps N] [--from T] [--until T] [--sheet SHEET.png] "
        "VIDEO")
    assert "--cue-changes" not in out and "SCRIPT" not in out


def test_run_as_a_program_it_prints_and_writes_what_it_does_when_called_inside_the_test(short, ffstub, tmp_path):
    as_program = run_program("stills", short, "--at", "0,3", "--out", tmp_path / "a", "--sheet", tmp_path / "a.png",
                             env=ffstub)
    inside = run("stills", short, "--at", "0,3", "--out", tmp_path / "b", "--sheet", tmp_path / "b.png", env=ffstub)
    assert as_program[0] == 0 and as_program[1].startswith("t0000.00.png at 0.000 s\n")
    code, out, err = inside     # the same run into b, so its paths name b where the program's name a
    assert as_program == (code, out.replace(str(tmp_path / "b"), str(tmp_path / "a")),
                          err.replace(str(tmp_path / "b"), str(tmp_path / "a")))
    assert sorted(os.listdir(tmp_path / "a")) == sorted(os.listdir(tmp_path / "b"))
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()


def test_at_writes_one_png_a_time_at_the_videos_own_size_and_lists_them(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, out, err = run("stills", short, "--at", "0,1.5,3", "--out", folder, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0001.50.png", "t0003.00.png"]
    for name, colour in [("t0000.00.png", (10, 20, 30)), ("t0001.50.png", (10, 20, 30)), ("t0003.00.png", (40, 50, 60))]:
        im = Image.open(folder / name)
        assert (im.size, im.getpixel((0, 0))[:3], im.getpixel((479, 853))[:3]) == ((480, 854), colour, colour)
    assert (folder / "stills.txt").read_text() == "0.00 t0000.00.png\n1.50 t0001.50.png\n3.00 t0003.00.png\n"
    assert out.splitlines() == ["t0000.00.png at 0.000 s", "t0001.50.png at 1.500 s", "t0003.00.png at 3.000 s",
                                f"Wrote 3 stills to {folder}"]
    calls = ff_calls(ffstub)
    assert [next(iter(c)) for c in calls] == ["ffprobe", "ffmpeg", "ffmpeg", "ffmpeg"]
    for call, at in zip(calls[1:], ("0.000", "1.500", "3.000")):
        args = call["ffmpeg"]
        assert args[args.index("-ss") + 1] == at and args[args.index("-s") + 1] == "480x854" and args[-1] == "-"


def test_every_takes_a_frame_every_n_seconds_from_zero_while_less_than_the_length(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, out, err = run("stills", short, "--every", "2", "--out", folder, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0002.00.png", "t0004.00.png", "t0006.00.png",
                                          "t0008.00.png"]                 # 8 < 8.342; 10 would be past the end
    assert (folder / "stills.txt").read_text().splitlines()[-1] == "8.00 t0008.00.png"
    assert out.splitlines()[-1] == f"Wrote 5 stills to {folder}"
    assert [c["ffmpeg"][c["ffmpeg"].index("-ss") + 1] for c in ff_calls(ffstub)[1:]] == \
        ["0.000", "2.000", "4.000", "6.000", "8.000"]


def test_every_of_zero_or_less_is_refused_before_ffmpeg_runs(short, ffstub, tmp_path):
    for bad in ("0", "-1"):
        code, out, err = run("stills", short, "--every", bad, "--out", tmp_path / "stills", env=ffstub)
        assert (code, out, err) == (2, "", "stills: --every must be more than 0\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "stills").exists()


def test_changes_takes_the_first_frame_and_each_cut_ffmpeg_reports_with_the_threshold_as_data(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, _out, err = run("stills", short, "--changes", "--out", folder, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0002.00.png", "t0004.04.png"]
    assert Image.open(folder / "t0004.04.png").getpixel((0, 0))[:3] == (70, 80, 90)
    assert (folder / "stills.txt").read_text() == "0.00 t0000.00.png\n2.00 t0002.00.png\n4.04 t0004.04.png\n"
    calls = ff_calls(ffstub)
    assert [next(iter(c)) for c in calls] == ["ffprobe", "ffmpeg", "ffmpeg", "ffmpeg", "ffmpeg"]
    scan = calls[1]["ffmpeg"]
    assert scan[scan.index("-vf") + 1] == "fps=10,select='gt(scene,0.3)',metadata=print"   # one argument, never shell text; training-video-tools' item 28: at 10 fps
    assert scan[scan.index("-f") + 1] == "null" and scan[-1] == "-" and "-nostdin" in scan
    assert [c["ffmpeg"][c["ffmpeg"].index("-ss") + 1] for c in calls[2:]] == ["0.000", "2.000", "4.040"]
    code, _out, err = run("stills", short, "--changes", "--threshold", "0.55", "--out", tmp_path / "again", env=ffstub)
    scan = ff_calls(ffstub)[6]["ffmpeg"]
    assert code == 0 and scan[scan.index("-vf") + 1] == "fps=10,select='gt(scene,0.55)',metadata=print"


@pytest.mark.parametrize("flags, message", [
    ([], "choose how to pick the frames of a video file: --at, --every or --changes"),
    (["--at", "1", "--every", "2"], "give one of --at, --every and --changes, not --at and --every"),
    (["--at", "1", "--changes"], "give one of --at, --every and --changes, not --at and --changes"),
    (["--every", "2", "--changes", "--threshold", "0.4"], "give one of --at, --every and --changes, not --every and --changes"),
    (["--at", "1", "--threshold", "0.4"], "--threshold goes with --changes"),
    (["--changes", "--threshold", "1.5"], "--threshold should be a number from 0 to 1, not '1.5'"),
    (["--at", "1", "--grid", "3"], "--grid should be COLUMNSxROWS, not '3'"),
    (["--every", "10", "--sheet", "s.png", "--grid", "0x3"], "--grid needs at least one column and one row, not '0x3'"),
    (["--at", "1", "--grid=-1x2"], "--grid needs at least one column and one row, not '-1x2'"),   # argparse: -1x2 is an option otherwise
    (["--at", "1,x"], "--at: 'x' is not a time in seconds"),
])
def test_a_bad_choice_of_frames_is_refused_before_ffmpeg_runs(short, ffstub, tmp_path, flags, message):
    code, out, err = run("stills", short, *flags, "--out", tmp_path / "stills", env=ffstub)
    assert (code, out, err) == (2, "", f"stills: {message}\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "stills").exists()


def test_a_time_past_the_end_is_refused_naming_the_length_and_nothing_is_written(short, ffstub, tmp_path):
    code, out, err = run("stills", short, "--at", "1,8.342,2", "--out", tmp_path / "stills", env=ffstub)
    assert (code, out, err) == (2, "", f"stills: 8.342 s is past the end of {short} (8.342 s)\n")
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe"] and not (tmp_path / "stills").exists()


def test_an_existing_still_or_listing_is_never_written_over_and_the_folder_is_left_as_it_was(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir()
    (folder / "t0001.50.png").write_bytes(b"mine")
    (folder / "notes.md").write_text("keep\n")
    code, out, err = run("stills", short, "--at", "0,1.5", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 't0001.50.png'} already exists; give a new name\n")
    assert sorted(os.listdir(folder)) == ["notes.md", "t0001.50.png"] and (folder / "t0001.50.png").read_bytes() == b"mine"
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe"]           # no frame was read
    (folder / "t0001.50.png").unlink()
    (folder / "stills.txt").write_text("mine\n")
    code, out, err = run("stills", short, "--changes", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 'stills.txt'} already exists; give a new name\n")
    assert sorted(os.listdir(folder)) == ["notes.md", "stills.txt"] and (folder / "stills.txt").read_text() == "mine\n"
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe", "ffprobe"]   # refused before the scan


STRIP = (0x55, 0x55, 0x55)


def test_the_sheet_keeps_a_vertical_videos_proportions_in_360_wide_cells_with_the_label_under_each(short, ffstub, tmp_path):
    folder, sheet = tmp_path / "stills", tmp_path / "sheet.png"
    code, out, err = run("stills", short, "--at", "0,2,4.04", "--out", folder, "--sheet", sheet, env=ffstub)
    assert (code, err) == (0, "")
    im = Image.open(sheet)
    assert im.size == (720, 1354)                                    # 3 frames: 2x2 cells of 360 x (641 + 36)
    assert im.getpixel((10, 10))[:3] == (10, 20, 30)                 # frame 1, top left
    assert im.getpixel((359, 639))[:3] == (10, 20, 30)               # frame 1 fills its 360x640
    assert im.getpixel((10, 640 + 5))[:3] == STRIP                   # its label strip, under it
    assert im.getpixel((360 + 10, 10))[:3] == (40, 50, 60)           # frame 2
    assert im.getpixel((10, 677 + 10))[:3] == (70, 80, 90)           # frame 3, second row
    assert im.getpixel((360 + 10, 677 + 10))[:3] == (255, 255, 255)  # the empty fourth cell
    assert out.splitlines()[-1] == f"Wrote 3 stills to {folder} and the sheet {sheet}"
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0002.00.png", "t0004.04.png"]


def test_a_landscape_video_gets_short_cells_and_a_given_grid_spreads_over_numbered_sheets(ffstub, tmp_path):
    wide = fake_media(str(tmp_path / "wide.mp4"), duration="8.342", frames="250", width="854", height="480",
                      colours="0:10.20.30,4:40.50.60")
    folder, sheet = tmp_path / "stills", tmp_path / "s.png"
    code, out, err = run("stills", wide, "--every", "4", "--out", folder, "--sheet", sheet, "--grid", "2x1", env=ffstub)
    assert (code, err) == (0, "")
    assert not sheet.exists()
    one, two = Image.open(tmp_path / "s-1.png"), Image.open(tmp_path / "s-2.png")
    assert one.size == two.size == (720, 239)                         # 2x1 cells of 360 x (203 + 36)
    assert one.getpixel((10, 10))[:3] == (10, 20, 30) and one.getpixel((370, 10))[:3] == (40, 50, 60)   # 0 s, 4 s
    assert one.getpixel((10, 201))[:3] == (10, 20, 30) and one.getpixel((10, 202 + 5))[:3] == STRIP
    assert two.getpixel((10, 10))[:3] == (40, 50, 60) and two.getpixel((370, 10))[:3] == (255, 255, 255)   # 8 s, then empty
    assert out.splitlines()[-1] == f"Wrote 3 stills to {folder} and 2 sheets {tmp_path / 's-1.png'}, {tmp_path / 's-2.png'}"


def test_an_existing_sheet_is_refused_before_anything_is_read_or_written(short, ffstub, tmp_path):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"mine")
    code, out, err = run("stills", short, "--at", "0", "--out", tmp_path / "stills", "--sheet", sheet, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {sheet} already exists; give a new name\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "stills").exists() and sheet.read_bytes() == b"mine"
    (tmp_path / "s-2.png").write_bytes(b"mine")
    code, out, err = run("stills", short, "--at", "0,1,2", "--grid", "1x1", "--out", tmp_path / "stills",
                         "--sheet", tmp_path / "s.png", env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {tmp_path / 's-2.png'} already exists; give a new name\n")
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe"] and not (tmp_path / "stills").exists()


@pytest.mark.parametrize("name", ["script.md", "NOTES.MD"])
def test_a_training_script_is_refused_saying_its_forms_are_training_video_tools(ffstub, tmp_path, name):
    script = tmp_path / name
    script.write_text("# A training video\n")
    code, out, err = run("stills", script, "--at", "1", "--out", tmp_path / "stills", env=ffstub)
    assert (code, out) == (2, "")
    assert err == (f"stills: {script}: stills here takes a video file; the forms that take a training script "
                   "(stills SCRIPT.md …) are training-video-tools'\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "stills").exists()


def test_without_ffmpeg_the_video_form_says_so_and_a_failing_frame_is_reported_with_what_stays(short, ffstub, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    code, out, err = run("stills", short, "--at", "0", "--out", tmp_path / "stills", env={"PATH": str(empty)})
    assert (code, out, err) == (4, "", "stills: ffmpeg is not on PATH; install ffmpeg as the README says\n")
    code, out, err = run("stills", short, "--at", "0,1", "--out", tmp_path / "stills", env={**ffstub, "FFSTUB_FAIL": "frame"})
    assert code == 4 and out == ""
    assert err.startswith(f"stills: ffmpeg failed (exit 1) reading the frame of {short} at 0.000 s; its output follows\n")
    assert os.listdir(tmp_path / "stills") == []                    # the first frame failed: nothing kept, no listing


def test_a_frame_ffmpeg_gives_short_is_an_error_naming_the_sizes_and_nothing_is_kept(short, ffstub, tmp_path):
    code, out, err = run("stills", short, "--at", "1", "--out", tmp_path / "stills", env={**ffstub, "FFSTUB_SHORT_FRAME": "1"})
    assert (code, out) == (4, "")
    assert err == (f"stills: ffmpeg gave 614880 bytes for the frame of {short} at 1.000 s, not the 1229760 of a "
                   "480x854 frame; is the file that long?\n")
    assert os.listdir(tmp_path / "stills") == []


def test_names_with_spaces_and_non_ascii_pass_through_as_data(ffstub, tmp_path):
    video = fake_media(str(tmp_path / "clips élan" / "my video 'q' $x.mp4"), duration="3", frames="90",
                       width="480", height="854", colours="0:1.2.3", scenes="1.5")
    folder = tmp_path / "stills für \"q\""
    code, _out, err = run("stills", video, "--changes", "--out", folder, "--sheet", folder / "sheet ß.png", env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["sheet ß.png", "stills.txt", "t0000.00.png", "t0001.50.png"]
    scan = ff_calls(ffstub)[1]["ffmpeg"]
    assert scan[scan.index("-i") + 1] == video                       # the path is one argument, as given


# training-video-tools' item 28: a cheaper detection and a time window.

def test_the_scan_samples_at_10_fps_and_skips_the_audio_and_the_frame_reads_do_not(short, ffstub, tmp_path):
    code, _out, err = run("stills", short, "--changes", "--out", tmp_path / "stills", env=ffstub)
    assert (code, err) == (0, "")
    calls = ff_calls(ffstub)
    scan = calls[1]["ffmpeg"]
    assert scan[scan.index("-vf") + 1] == "fps=10,select='gt(scene,0.3)',metadata=print"
    assert scan.index("-an") > scan.index("-i") and "-ss" not in scan and "-to" not in scan and "-copyts" not in scan
    for c in calls[2:]:
        read = c["ffmpeg"]
        assert "-vf" not in read and "-an" not in read and "fps=" not in " ".join(read)


def test_detect_fps_sets_the_scans_rate_as_data_and_is_refused_when_not_a_rate_or_without_changes(short, ffstub, tmp_path):
    code, out, err = run("stills", short, "--changes", "--detect-fps", "5", "--out", tmp_path / "stills", env=ffstub)
    assert (code, err) == (0, "")
    scan = ff_calls(ffstub)[1]["ffmpeg"]
    assert scan[scan.index("-vf") + 1] == "fps=5,select='gt(scene,0.3)',metadata=print"
    for flags, message in [
        (["--changes", "--detect-fps", "0"], "--detect-fps should be a number above 0, not '0'"),
        (["--changes", "--detect-fps=-2"], "--detect-fps should be a number above 0, not '-2'"),
        (["--changes", "--detect-fps", "x"], "--detect-fps should be a number above 0, not 'x'"),
        (["--every", "2", "--detect-fps", "5"], "--detect-fps goes with --changes"),
    ]:
        code, out, err = run("stills", short, *flags, "--out", tmp_path / "again", env=ffstub)
        assert (code, out, err) == (2, "", f"stills: {message}\n"), flags
    assert len(ff_calls(ffstub)) == 5 and not (tmp_path / "again").exists()      # the probe, the scan, three frames; the refusals ran nothing


def test_every_with_a_window_steps_from_the_start_while_less_than_until(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, _out, err = run("stills", short, "--every", "2", "--from", "3", "--until", "7", "--out", folder, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0003.00.png", "t0005.00.png"]
    assert (folder / "stills.txt").read_text() == "3.00 t0003.00.png\n5.00 t0005.00.png\n"
    assert [c["ffmpeg"][c["ffmpeg"].index("-ss") + 1] for c in ff_calls(ffstub)[1:]] == ["3.000", "5.000"]


def test_changes_with_a_window_seeks_the_scan_on_the_files_clock_and_lists_no_first_frame(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, _out, err = run("stills", short, "--changes", "--from", "3", "--until", "8.342", "--out", folder, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0004.04.png"]            # the cut at 2 is before the window
    assert (folder / "stills.txt").read_text() == "4.04 t0004.04.png\n"
    scan = ff_calls(ffstub)[1]["ffmpeg"]
    before = scan[:scan.index("-i")]
    assert before[before.index("-ss") + 1] == "3.000" and before[before.index("-to") + 1] == "8.342" and "-copyts" in before
    assert scan[scan.index("-vf") + 1] == "fps=10,select='gt(scene,0.3)',metadata=print" and "-an" in scan
    code, _out, err = run("stills", short, "--changes", "--from", "0", "--until", "3", "--out", tmp_path / "first", env=ffstub)
    assert code == 0 and sorted(os.listdir(tmp_path / "first")) == ["stills.txt", "t0000.00.png", "t0002.00.png"]  # from 0: the first frame


def listing(folder):
    return (folder / "stills.txt").read_text()


def test_two_slices_into_one_folder_give_what_one_whole_run_gives_for_changes_and_for_every(short, ffstub, tmp_path):
    whole, sliced = tmp_path / "whole", tmp_path / "sliced"
    assert run("stills", short, "--changes", "--out", whole, env=ffstub)[0] == 0
    code, out, err = run("stills", short, "--changes", "--from", "0", "--until", "4", "--out", sliced, env=ffstub)
    assert (code, err) == (0, "") and listing(sliced) == "0.00 t0000.00.png\n2.00 t0002.00.png\n"
    code, out, err = run("stills", short, "--changes", "--from", "4", "--out", sliced, env=ffstub)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(sliced)) == sorted(os.listdir(whole)) and listing(sliced) == listing(whole)
    assert out.splitlines()[-1] == f"Wrote 1 still to {sliced}"
    whole, sliced = tmp_path / "whole-every", tmp_path / "sliced-every"
    assert run("stills", short, "--every", "3", "--out", whole, env=ffstub)[0] == 0
    assert run("stills", short, "--every", "3", "--until", "3", "--out", sliced, env=ffstub)[0] == 0      # [0, 3): 0
    assert run("stills", short, "--every", "3", "--from", "3", "--until", "100", "--out", sliced, env=ffstub)[0] == 0   # [3, end): 3, 6
    assert sorted(os.listdir(sliced)) == sorted(os.listdir(whole)) == ["stills.txt", "t0000.00.png", "t0003.00.png", "t0006.00.png"]
    assert listing(sliced) == listing(whole)


def test_a_slice_refuses_a_still_already_there_and_a_whole_run_refuses_an_existing_listing(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    assert run("stills", short, "--changes", "--until", "4", "--out", folder, env=ffstub)[0] == 0
    before = sorted(os.listdir(folder)), listing(folder)
    code, out, err = run("stills", short, "--changes", "--from", "0", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 't0000.00.png'} already exists; give a new name\n")
    code, out, err = run("stills", short, "--changes", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 'stills.txt'} already exists; give a new name\n")
    assert (sorted(os.listdir(folder)), listing(folder)) == before


def test_the_listing_is_written_a_line_at_a_time_so_a_run_that_dies_leaves_what_it_wrote_listed(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    code, out, err = run("stills", short, "--at", "0,1,3", "--out", folder, env={**ffstub, "FFSTUB_FAIL": "frame@3.000"})
    assert code == 4 and out.splitlines() == ["t0000.00.png at 0.000 s", "t0001.00.png at 1.000 s"]
    assert err.startswith(f"stills: ffmpeg failed (exit 1) reading the frame of {short} at 3.000 s; its output follows\n")
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0001.00.png"]
    assert listing(folder) == "0.00 t0000.00.png\n1.00 t0001.00.png\n"


def test_sheet_alone_draws_the_folders_listing_in_its_order_reading_nothing_from_the_video(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    assert run("stills", short, "--changes", "--out", folder, env=ffstub)[0] == 0
    calls_before = len(ff_calls(ffstub))
    code, out, err = run("stills", short, "--sheet", folder / "sheet.png", "--out", folder, "--grid", "3x1", env=ffstub)
    assert (code, err) == (0, "") and out == f"Drew 3 stills from {folder / 'stills.txt'} on the sheet {folder / 'sheet.png'}\n"
    assert len(ff_calls(ffstub)) == calls_before                      # nothing read from the video
    im = Image.open(folder / "sheet.png")
    assert im.size == (3 * 360, -(-360 * 854 // 480) + sheet.STRIP)    # three cells across, one row
    assert im.getpixel((10, 10))[:3] == (10, 20, 30) and im.getpixel((370, 10))[:3] == (40, 50, 60) and im.getpixel((730, 10))[:3] == (70, 80, 90)


@pytest.mark.parametrize("prepare, message", [
    (lambda folder: None, "{folder}/stills.txt is missing; --sheet alone draws the stills a folder's listing names"),
    (lambda folder: (folder.mkdir(), (folder / "stills.txt").write_text("0.00 t0000.00.png\n")),
     "{folder}/stills.txt names t0000.00.png, which is not in {folder}"),
    (lambda folder: (folder.mkdir(), (folder / "stills.txt").write_text("0.00 t0000.00.png\nnot a line\n")),
     "{folder}/stills.txt: line 2 is not 'TIME NAME': not a line"),
])
def test_sheet_alone_refuses_a_missing_listing_or_still_or_a_bad_line_in_words(short, ffstub, tmp_path, prepare, message):
    folder = tmp_path / "stills"
    prepare(folder)
    code, out, err = run("stills", short, "--sheet", tmp_path / "sheet.png", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {message.format(folder=folder)}\n")
    assert not (tmp_path / "sheet.png").exists()


@pytest.mark.parametrize("flags, message", [
    (["--at", "1", "--from", "0"], "--from and --until go with --every or --changes, not --at"),
    (["--at", "1", "--until", "3"], "--from and --until go with --every or --changes, not --at"),
    (["--sheet", "s.png", "--from", "1"], "--from and --until need --every or --changes (--sheet alone draws a folder's listing)"),
    (["--every", "2", "--from", "x"], "--from: 'x' is not a time in seconds"),
])
def test_a_bad_window_on_the_command_is_refused_before_ffmpeg_runs(short, ffstub, tmp_path, flags, message):
    code, out, err = run("stills", short, *flags, "--out", tmp_path / "stills", env=ffstub)
    assert (code, out, err) == (2, "", f"stills: {message}\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "stills").exists()


def test_a_window_past_the_end_is_refused_naming_the_length_after_the_probe_only(short, ffstub, tmp_path):
    code, out, err = run("stills", short, "--every", "2", "--from", "9", "--out", tmp_path / "stills", env=ffstub)
    assert (code, out, err) == (2, "", "stills: --from 9 s is at or past the end of the video (8.342 s)\n")
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe"] and not (tmp_path / "stills").exists()


def test_sheet_alone_still_needs_the_video_file_to_exist(ffstub, tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir()
    (folder / "stills.txt").write_text("")
    code, out, err = run("stills", tmp_path / "gone.mp4", "--sheet", tmp_path / "sheet.png", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {tmp_path / 'gone.mp4'} is missing\n")
    assert ff_calls(ffstub) == [] and not (tmp_path / "sheet.png").exists()


def test_sheet_alone_refuses_an_existing_sheet_before_it_reads_the_listing(short, ffstub, tmp_path):
    sheet = tmp_path / "sheet.png"
    sheet.write_bytes(b"mine")
    code, out, err = run("stills", short, "--sheet", sheet, "--out", tmp_path / "no-such-folder", env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {sheet} already exists; give a new name\n")
    assert sheet.read_bytes() == b"mine"


def test_sheet_alone_refuses_an_empty_listing_in_words(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir()
    (folder / "stills.txt").write_text("")
    code, out, err = run("stills", short, "--sheet", tmp_path / "sheet.png", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 'stills.txt'} lists no stills; there is nothing to draw\n")
    assert not (tmp_path / "sheet.png").exists()


# training-video-tools' item 29: what a kill leaves is written over, a listed still is refused.

def test_a_folder_as_a_kill_leaves_it_is_finished_by_the_next_window_with_files_and_listing_agreeing(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir()
    (folder / "stills.txt").write_text("0.00 t0000.00.png\n")
    Image.new("RGB", (480, 854), (1, 2, 3)).save(folder / "t0000.00.png")
    Image.new("RGB", (480, 854), (9, 9, 9)).save(folder / "t0002.00.png")      # written, killed before its line
    (folder / ".t0004.04.png.part").write_bytes(b"half a png")                   # killed mid-write
    code, out, err = run("stills", short, "--changes", "--from", "2", "--out", folder, env=ffstub)
    assert code == 0 and err == "stills: t0002.00.png was there but not listed; written again\n"
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0000.00.png", "t0002.00.png", "t0004.04.png"]
    assert listing(folder) == "0.00 t0000.00.png\n2.00 t0002.00.png\n4.04 t0004.04.png\n"
    assert Image.open(folder / "t0002.00.png").getpixel((0, 0))[:3] == (40, 50, 60)     # the stub's frame, not the leftover
    assert Image.open(folder / "t0004.04.png").getpixel((0, 0))[:3] == (70, 80, 90)
    code, out, err = run("stills", short, "--sheet", folder / "sheet.png", "--out", folder, env=ffstub)
    assert code == 0 and out.startswith("Drew 3 stills")


def test_a_listed_still_is_refused_before_anything_is_read_even_beside_a_part_file(short, ffstub, tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir()
    (folder / "stills.txt").write_text("2.00 t0002.00.png\n")
    (folder / "t0002.00.png").write_bytes(b"png")
    (folder / ".t0004.04.png.part").write_bytes(b"half")
    code, out, err = run("stills", short, "--changes", "--from", "2", "--out", folder, env=ffstub)
    assert (code, out, err) == (3, "", f"stills: {folder / 't0002.00.png'} already exists; give a new name\n")
    assert [next(iter(c)) for c in ff_calls(ffstub)] == ["ffprobe", "ffmpeg"]      # the probe and the scan, no frame read
    assert sorted(os.listdir(folder)) == [".t0004.04.png.part", "stills.txt", "t0002.00.png"]
