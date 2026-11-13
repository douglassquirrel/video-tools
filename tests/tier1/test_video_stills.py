"""stills on a video file (training-video-tools' item 24): the times, the names, the grid and ffmpeg's scene report,
as pure functions."""

import os

import pytest

from videotools import cli, video_stills


def test_at_times_are_read_in_the_order_given_each_at_most_once():
    assert video_stills.parse_at("0,1.5,3") == [0.0, 1.5, 3.0]
    assert video_stills.parse_at("12.4, 3") == [12.4, 3.0]
    for bad, why in [("", "--at needs at least one time in seconds, such as 0,1.5,3"),
                     ("1,,2", "--at needs at least one time in seconds, such as 0,1.5,3"),
                     ("1,x", "--at: 'x' is not a time in seconds"),
                     ("1,-2", "--at: a time cannot be negative (-2)"),
                     ("1,2,1", "--at: 1 is given twice")]:
        with pytest.raises(cli.Failure) as e:
            video_stills.parse_at(bad)
        assert (str(e.value), e.value.code) == (why, cli.USAGE)


def test_every_n_seconds_runs_from_zero_while_less_than_the_length():
    assert video_stills.every_times(2, 7.0) == [0.0, 2.0, 4.0, 6.0]
    assert video_stills.every_times(2, 6.0) == [0.0, 2.0, 4.0]          # the end itself is not a frame
    assert video_stills.every_times(0.1, 0.35) == [0.0, 0.1, 0.2, 0.3]  # multiples, not a running sum
    for bad in (0, -1.5):
        with pytest.raises(cli.Failure) as e:
            video_stills.every_times(bad, 7.0)
        assert (str(e.value), e.value.code) == ("--every must be more than 0", cli.USAGE)


def test_a_still_is_named_by_its_time_so_names_sort_in_time_order():
    assert video_stills.still_name(12.4) == "t0012.40.png"
    assert video_stills.still_name(0) == "t0000.00.png"
    assert video_stills.still_name(1.005) == "t0001.00.png"          # two decimals, as the label
    assert video_stills.still_name(12345.678) == "t12345.68.png"     # the width grows past four digits
    names = [video_stills.still_name(t) for t in (0, 1.5, 3, 12.4, 100)]
    assert sorted(names) == names
    assert video_stills.label(12.4) == "12.40 s"
    assert video_stills.listing_line(12.4) == "12.40 t0012.40.png"


def test_the_default_grid_is_the_smallest_square_that_holds_the_frames_at_most_five_across():
    assert [video_stills.choose_grid(n) for n in (1, 2, 4, 5, 9, 10, 25)] == \
        [(1, 1), (2, 1), (2, 2), (3, 2), (3, 3), (4, 3), (5, 5)]
    assert video_stills.choose_grid(26) == (5, 6)                    # never wider than 5 cells (1800 px)
    assert video_stills.choose_grid(31) == (5, 7)


def test_a_cell_is_360_wide_and_as_tall_as_the_video_needs_plus_the_label_strip():
    assert video_stills.cell_size(480, 854) == (360, 641 + 36)       # a vertical Short keeps its proportions
    assert video_stills.cell_size(854, 480) == (360, 203 + 36)       # landscape; 640.5 and 202.3 rounded up,
    assert video_stills.cell_size(1920, 1080) == (360, 203 + 36)     # so the frame fits at the full 360 wide
    from videotools import sheet
    assert sheet.frame_size(video_stills.cell_size(480, 854), (480, 854)) == (360, 640)
    assert sheet.frame_size(video_stills.cell_size(854, 480), (854, 480)) == (360, 202)


REPORT = """[Parsed_metadata_1 @ 0x7a0c62280] frame:0    pts:25600   pts_time:2
[Parsed_metadata_1 @ 0x7a0c62280] lavfi.scene_score=0.400000
[Parsed_metadata_1 @ 0x7a0c62280] frame:1    pts:51200   pts_time:4.04
[Parsed_metadata_1 @ 0x7a0c62280] lavfi.scene_score=0.350000
"""   # the shape real ffmpeg 9.0.2 printed (training-video-tools' PLAN.md, "Things checked", 17 October 2026)


def test_the_changes_are_the_first_frame_then_each_pts_time_of_ffmpegs_scene_report():
    assert video_stills.change_times(REPORT) == [0.0, 2.0, 4.04]
    assert video_stills.change_times("") == [0.0]                    # no cut: the first frame alone
    assert video_stills.change_times("frame:0 pts:0 pts_time:0\n") == [0.0]   # a cut at 0 is not twice


def test_the_threshold_is_a_number_from_0_to_1():
    assert video_stills.parse_threshold("0.3") == 0.3
    assert (video_stills.parse_threshold("0"), video_stills.parse_threshold("1")) == (0.0, 1.0)
    for bad in ("1.5", "-0.1", "x"):
        with pytest.raises(cli.Failure) as e:
            video_stills.parse_threshold(bad)
        assert (str(e.value), e.value.code) == (f"--threshold should be a number from 0 to 1, not '{bad}'", cli.USAGE)


def test_a_grid_needs_two_whole_numbers_each_at_least_one():
    assert video_stills.parse_grid("3x2") == (3, 2)
    assert video_stills.parse_grid("1X1") == (1, 1)
    assert video_stills.parse_grid(None) is None
    for bad in ("0x3", "3x0", "0x0", "-1x2"):
        with pytest.raises(cli.Failure) as e:
            video_stills.parse_grid(bad)
        assert (str(e.value), e.value.code) == (f"--grid needs at least one column and one row, not '{bad}'", cli.USAGE)
    for bad in ("2x", "x", "3", "2x2x2", "axb"):
        with pytest.raises(cli.Failure) as e:
            video_stills.parse_grid(bad)
        assert (str(e.value), e.value.code) == (f"--grid should be COLUMNSxROWS, not '{bad}'", cli.USAGE)


# Item 28: a time window.

def test_every_times_step_from_a_start_while_less_than_the_end():
    assert video_stills.every_times(2, 8.342, 3) == [3.0, 5.0, 7.0]
    assert video_stills.every_times(2, 7.0, 3) == [3.0, 5.0]          # the end itself is not a frame
    assert video_stills.every_times(0.1, 0.35, 0.1) == [0.1, 0.2, 0.3]  # multiples from the start, no drift


def test_a_window_is_from_and_until_in_seconds_with_until_held_to_the_length():
    assert video_stills.parse_window(None, None, 8.342) == (0.0, 8.342)
    assert video_stills.parse_window("3", "7.5", 8.342) == (3.0, 7.5)
    assert video_stills.parse_window("3", None, 8.342) == (3.0, 8.342)
    assert video_stills.parse_window(None, "4", 8.342) == (0.0, 4.0)
    assert video_stills.parse_window("6", "100", 8.342) == (6.0, 8.342)   # past the end: the end


@pytest.mark.parametrize("start, end, message", [
    ("x", None, "--from: 'x' is not a time in seconds"),
    (None, "y", "--until: 'y' is not a time in seconds"),
    ("-1", None, "--from: a time cannot be negative (-1)"),
    (None, "-0.5", "--until: a time cannot be negative (-0.5)"),
    ("8.342", None, "--from 8.342 s is at or past the end of the video (8.342 s)"),
    ("9", None, "--from 9 s is at or past the end of the video (8.342 s)"),
    ("3", "3", "--until (3 s) must be after --from (3 s)"),
    ("3", "2", "--until (2 s) must be after --from (3 s)"),
])
def test_a_bad_window_is_refused_in_words(start, end, message):
    with pytest.raises(cli.Failure) as e:
        video_stills.parse_window(start, end, 8.342)
    assert (str(e.value), e.value.code) == (message, 2)


# Item 29: a still is written to a part name, listed, then renamed.

class Saver:
    """Stands in for a PIL image: records the path it is asked to save to and writes a file there."""

    def __init__(self):
        self.saved_to = []

    def save(self, path, format=None):
        self.saved_to.append(path)
        with open(path, "wb") as f:
            f.write(b"png")


def test_a_still_is_saved_to_a_part_name_listed_and_only_then_renamed(tmp_path):
    folder = str(tmp_path)
    img = Saver()
    video_stills.write_still(img, folder, 1.0)
    assert img.saved_to == [os.path.join(folder, ".t0001.00.png.part")]
    assert sorted(os.listdir(folder)) == ["stills.txt", "t0001.00.png"]
    assert (tmp_path / "stills.txt").read_text() == "1.00 t0001.00.png\n"


def test_a_still_is_not_renamed_when_its_line_cannot_be_written(tmp_path):
    (tmp_path / "stills.txt").mkdir()                   # the listing cannot be appended to
    img = Saver()
    with pytest.raises(OSError):
        video_stills.write_still(img, str(tmp_path), 1.0)
    assert sorted(os.listdir(tmp_path)) == [".t0001.00.png.part", "stills.txt"]   # no named still unlisted


def test_a_cut_at_or_after_the_windows_end_is_not_listed():
    report = "[x] frame:0 pts:0 pts_time:2.5\n[x] frame:1 pts:0 pts_time:3\n[x] frame:2 pts:0 pts_time:3.5\n"
    assert video_stills.change_times(report, (2.0, 3.0)) == [2.5]
    assert video_stills.change_times(report) == [0.0, 2.5, 3.0, 3.5]


def test_a_listing_line_with_more_than_a_time_and_a_name_is_refused(tmp_path):
    listing = tmp_path / "stills.txt"
    listing.write_text("0.00 t0000.00.png\n1.00 t0001.00.png extra\n")
    with pytest.raises(cli.Failure) as e:
        video_stills.read_listing(str(listing))
    assert str(e.value) == f"{listing}: line 2 is not 'TIME NAME': 1.00 t0001.00.png extra"
