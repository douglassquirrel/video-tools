"""The description table of narrate --lines (training-video-tools' item 26): columns by header, in any order; every
refusal in words; the clip names, the overrun and the estimate."""

import pytest

from videotools import cli, lines

TABLE = """# Golden Hour (invented)

Notes above the table are ignored, | pipes | and all.

| # | Start (s) | Words | Est. end (s) | Over | Checked against | Line |
|---|---|---|---|---|---|---|
| 1 | 0.10 | 5 | 1.10 | gap | stills 0.00 | A kite climbs over the wall. |
| 2 | 4.00 | 3 | 4.60 | "Hello" | — | On screen: “Harbour”, it's dusk; gulls wheel. |
| 3 | 9.50 | 2 | 9.90 |  | — | Dips \\| rises. |

Notes below are ignored too.
"""


def test_the_columns_are_found_by_header_in_any_order_and_the_rest_ignored():
    assert lines.parse(TABLE, "script.md") == [
        {"n": 1, "start": 0.1, "text": "A kite climbs over the wall."},
        {"n": 2, "start": 4.0, "text": "On screen: “Harbour”, it's dusk; gulls wheel."},
        {"n": 3, "start": 9.5, "text": "Dips | rises."},                # an escaped pipe is a pipe
    ]
    shuffled = "| Line | Start (s) | # |\n|---|---|---|\n| First one. | 2.5 | 7 |\n| Second. | 2.75 | 8 |\n"
    assert lines.parse(shuffled, "x.md") == [{"n": 7, "start": 2.5, "text": "First one."},
                                              {"n": 8, "start": 2.75, "text": "Second."}]
    assert lines.parse("|#|Start (s)|Line|\n|-|-|-|\n|1|0|Tight cells.|\n", "x.md") == \
        [{"n": 1, "start": 0.0, "text": "Tight cells."}]


def test_an_earlier_table_without_the_three_columns_is_passed_over():
    text = "| Scene | Notes |\n|---|---|\n| 1 | dusk |\n\n| # | Start (s) | Line |\n|---|---|---|\n| 1 | 0.5 | Gulls. |\n"
    assert lines.parse(text, "x.md") == [{"n": 1, "start": 0.5, "text": "Gulls."}]


def table(*rows, header="| # | Start (s) | Words | Line |"):
    return "\n".join([header, "|---|---|---|---|"] + list(rows)) + "\n"


@pytest.mark.parametrize("text, message", [
    ("Just prose, no table.\n", "x.md has no table with the columns '#', 'Start (s)' and 'Line'"),
    ("| # | Start (s) | Words |\n|---|---|---|\n| 1 | 0 | 2 |\n",
     "the table in x.md has no 'Line' column (its columns are '#', 'Start (s)', 'Words')"),
    ("| No | Start | Line |\n|---|---|---|\n| 1 | 0 | Hi. |\n",
     "the table in x.md has no '#' or 'Start (s)' column (its columns are 'No', 'Start', 'Line')"),
    (table("| a | 0.10 | 1 | Hi. |"), "row 1 of the table in x.md: '#' should be a whole number from 1, not 'a'"),
    (table("| 0 | 0.10 | 1 | Hi. |"), "row 1 of the table in x.md: '#' should be a whole number from 1, not '0'"),
    (table("| 1 | 0.10 | 1 | Hi. |", "| 1 | 2.00 | 1 | Again. |"), "row 2 of the table in x.md: '#' 1 is given twice"),
    (table("| 1 | soon | 1 | Hi. |"), "row 1 of the table in x.md: 'Start (s)' should be seconds, not 'soon'"),
    (table("| 1 | -1 | 1 | Hi. |"), "row 1 of the table in x.md: 'Start (s)' cannot be negative (-1)"),
    (table("| 1 | 0.10 | 1 |  |"), "row 1 of the table in x.md: 'Line' is empty"),
    (table("| 1 | 0.10 | Hi. |"), "row 1 of the table in x.md has 3 cells where the header has 4"),
    (table(), "the table in x.md has no rows"),
])
def test_a_table_that_cannot_be_spoken_is_refused_in_words(text, message):
    with pytest.raises(cli.Failure) as e:
        lines.parse(text, "x.md")
    assert (str(e.value), e.value.code) == (message, cli.REFUSED)


def test_clips_are_named_by_number_with_as_many_digits_as_the_largest_needs():
    assert lines.clip_name(1, 14) == "01.wav" and lines.clip_name(14, 14) == "14.wav"
    assert lines.clip_name(1, 9) == "01.wav"                              # never fewer than two
    assert lines.clip_name(7, 120) == "007.wav"


def test_a_line_that_runs_past_the_next_lines_start_is_warned_about_naming_both():
    spoken = [({"n": 1, "start": 0.1, "text": "a"}, 2.0), ({"n": 2, "start": 2.5, "text": "b"}, 3.21),
              ({"n": 3, "start": 5.0, "text": "c"}, 1.0)]
    assert lines.overrun(spoken, 0) is None                               # 0.1 + 2.0 = 2.1 ≤ 2.5
    assert lines.overrun(spoken, 1) == "line 2 (at 2.50 s, 3.21 s long) runs 0.71 s into line 3 (at 5.00 s)"
    assert lines.overrun(spoken, 2) is None                               # the last line has no next


def test_the_estimate_scales_the_words_a_second_by_the_speed():
    assert lines.estimate("one two three four five six seven eight nine ten eleven twelve thirteen", 1.0) == 5.0
    assert lines.estimate("one two three four five six seven eight nine ten eleven twelve thirteen", 2.0) == 2.5


def test_the_speed_must_be_within_what_the_model_accepts():
    assert lines.check_speed(2.0) == 2.0 and lines.check_speed(0.5) == 0.5
    for bad in (2.5, 0.4, 0):
        with pytest.raises(cli.Failure) as e:
            lines.check_speed(bad)
        assert (str(e.value), e.value.code) == (f"--speed should be from 0.5 to 2.0 (the model's range), not {bad:g}", cli.USAGE)


SAY = """| # | Start (s) | Say | Line |
|---|---|---|---|
| 1 | 0.10 | [[sˈɪləs]] smiles. | Silas smiles. |
| 2 | 2.00 |  | Thea nods. |
| 3 | 4.00 | Hugo sits, slowly. | Hugo sits. |
"""


def test_a_say_column_gives_what_is_spoken_and_an_empty_say_leaves_the_line_alone():
    assert lines.parse(SAY, "x.md") == [
        {"n": 1, "start": 0.1, "text": "Silas smiles.", "say": "[[sˈɪləs]] smiles."},
        {"n": 2, "start": 2.0, "text": "Thea nods."},                       # no 'say': spoken from Line
        {"n": 3, "start": 4.0, "text": "Hugo sits.", "say": "Hugo sits, slowly."},
    ]


@pytest.mark.parametrize("say, problem", [
    ("[[sˈɪləs smiles.", "'[[' at character 1 is never closed with ']]'"),
    ("Silas]] smiles.", "']]' at character 6 has no '[[' before it"),
    ("[[]] smiles.", "'[[]]' at character 1 is empty"),
    ("[[s#ləs]] smiles.", "'#' (U+0023) in '[[s#ləs]]' is not a symbol the voice knows"),
])
def test_a_say_whose_spans_are_wrong_is_refused_naming_its_row_and_the_problem(say, problem):
    text = f"| # | Start (s) | Line | Say |\n|---|---|---|---|\n| 1 | 0 | Fine. |  |\n| 2 | 1 | Silas smiles. | {say} |\n"
    with pytest.raises(cli.Failure) as e:
        lines.parse(text, "x.md")
    assert (str(e.value), e.value.code) == (f"row 2 of the table in x.md: 'Say': {problem}", cli.REFUSED)
