"""Tier 1: reading and writing SubRip (.srt) transcripts."""

import pytest

from videotools.srt import Cue, SrtError, format_srt, parse_srt

TWO_CUES = (
    "1\n"
    "00:00:01,000 --> 00:00:02,500\n"
    "Hello there.\n"
    "\n"
    "2\n"
    "00:01:02,250 --> 01:00:03,999\n"
    "Second cue,\n"
    "on two lines.\n"
)


def test_reads_each_cue_with_its_times_in_milliseconds_and_its_lines():
    assert parse_srt(TWO_CUES) == [
        Cue(1000, 2500, ["Hello there."]),
        Cue(62250, 3603999, ["Second cue,", "on two lines."]),
    ]


def test_writes_cues_numbered_from_one_with_comma_millisecond_times():
    cues = [Cue(0, 1500, ["One."]), Cue(3723004, 3725000, ["Two,", "lines."])]
    assert format_srt(cues) == (
        "1\n00:00:00,000 --> 00:00:01,500\nOne.\n\n"
        "2\n01:02:03,004 --> 01:02:05,000\nTwo,\nlines.\n\n"
    )


def test_what_is_written_reads_back_the_same():
    cues = [Cue(0, 1500, ["One."]), Cue(1500, 99999999, ["Ünïcödé “quotes” $HOME \\ </script>"])]
    assert parse_srt(format_srt(cues)) == cues


def test_reads_windows_line_endings_a_byte_order_mark_and_extra_blank_lines():
    text = "﻿1\r\n00:00:01.000 --> 00:00:02.000\r\nOne.\r\n\r\n\r\n2\r\n00:00:02,000 --> 00:00:03,000\r\nTwo."
    assert parse_srt(text) == [Cue(1000, 2000, ["One."]), Cue(2000, 3000, ["Two."])]


@pytest.mark.parametrize("text, line, message", [
    ("one\n00:00:01,000 --> 00:00:02,000\nHi.\n",
     1, "expected a cue number, found 'one'"),
    ("1\n00:00:01,000 --> 00:00:02,000\nHi.\n\n2\n00:00:03 --> 00:00:04\nBye.\n",
     6, "expected the cue's times as 00:00:00,000 --> 00:00:00,000, found '00:00:03 --> 00:00:04'"),
    ("1\n00:00:01,000 --> 00:00:02,000\nHi.\n\n2\n",
     5, "the transcript ends after a cue number, with no times"),
    ("1\n00:00:05,000 --> 00:00:04,000\nHi.\n",
     2, "the cue ends before it starts"),
    ("1\n00:00:01,000 --> 00:00:02,000\nHi.\n\n2\n00:00:01,000 --> 00:00:61,000\nBye.\n",
     6, "the seconds or minutes are 60 or more"),
])
def test_a_malformed_transcript_names_the_line(text, line, message):
    with pytest.raises(SrtError) as e:
        parse_srt(text)
    assert (e.value.line, e.value.message) == (line, message)
