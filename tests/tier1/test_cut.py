"""Tier 1: where the cut falls, and what the cut transcript holds."""

import pytest

from videotools.cut import Cut, CutError, locate
from videotools.srt import Cue

CUES = [
    Cue(0, 4000, ["Is this thing on?"]),
    Cue(4000, 9500, ["Welcome to the show."]),
    Cue(9500, 15000, ["Today, cutting video."]),
    Cue(15000, 21000, ["That's all,", "thank you."]),
    Cue(21000, 25000, ["Is it off yet?"]),
]
LENGTH = 26000


def test_cuts_from_the_start_of_the_cue_where_from_begins_to_the_end_of_the_cue_where_to_ends():
    assert locate(CUES, "welcome to", "that's all thank you", LENGTH) == Cut(4000, 21000, 1, 3)


def test_without_from_the_video_keeps_its_beginning():
    assert locate(CUES, None, "cutting video", LENGTH) == Cut(0, 15000, 0, 2)


def test_without_to_the_video_keeps_its_end():
    assert locate(CUES, "today", None, LENGTH) == Cut(9500, 26000, 2, 4)


def test_the_end_is_never_after_the_end_of_the_video():
    assert locate(CUES, "today", "off yet", 23000) == Cut(9500, 23000, 2, 4)


def test_refuses_a_phrase_that_is_not_found():
    with pytest.raises(CutError) as e:
        locate(CUES, "goodbye", None, LENGTH)
    assert (e.value.code, e.value.message) == (5, 'the --from phrase "goodbye" is not in the transcript')


def test_refuses_a_phrase_found_more_than_once_giving_the_time_of_each():
    with pytest.raises(CutError) as e:
        locate(CUES, None, "is", LENGTH)
    assert (e.value.code, e.value.message) == (
        6, ('the --to phrase "is" is found 2 times, at 00:00:00.000 and 00:00:21.000: '
           'give a longer phrase, found only once'))


def test_refuses_an_end_before_the_start():
    with pytest.raises(CutError) as e:
        locate(CUES, "today", "welcome", LENGTH)
    assert (e.value.code, e.value.message) == (
        7, "the --to phrase ends at 00:00:09.500, not after the --from phrase begins at 00:00:09.500")


def test_refuses_a_start_at_or_after_the_end_of_the_video():
    with pytest.raises(CutError) as e:
        locate(CUES, "off yet", None, 20000)
    assert (e.value.code, e.value.message) == (
        7, "the --from phrase begins at 00:00:21.000, after the video ends at 00:00:20.000")


def test_the_cut_transcript_keeps_the_cues_in_the_cut_moved_back_by_the_start_and_numbered_from_one():
    from videotools.cut import cut_cues
    from videotools.srt import format_srt
    kept = cut_cues(CUES, Cut(4000, 21000, 1, 3))
    assert kept == [Cue(0, 5500, ["Welcome to the show."]), Cue(5500, 11000, ["Today, cutting video."]),
                    Cue(11000, 17000, ["That's all,", "thank you."])]
    assert format_srt(kept).startswith("1\n00:00:00,000 --> 00:00:05,500\nWelcome")


def test_cue_times_are_kept_inside_the_cut():
    from videotools.cut import cut_cues
    overlapping = [Cue(1000, 5000, ["a"]), Cue(3000, 9000, ["b"])]
    assert cut_cues(overlapping, Cut(3000, 8000, 0, 1)) == [Cue(0, 2000, ["a"]), Cue(0, 5000, ["b"])]


def test_the_plain_text_is_one_cue_per_line_without_times():
    from videotools.cut import plain_text
    assert plain_text(CUES[2:4]) == "Today, cutting video.\nThat's all, thank you.\n"


def test_ffmpeg_seeks_exactly_keeps_the_first_video_and_audio_and_reencodes():
    from videotools.cut import ffmpeg_args
    assert ffmpeg_args("/v/my talk.mov", Cut(4000, 21250, 1, 3), "/out/.my talk-cut.mp4.part") == [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", "4.000", "-i", "/v/my talk.mov", "-t", "17.250",
        "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart",
        "-f", "mp4", "/out/.my talk-cut.mp4.part"]
