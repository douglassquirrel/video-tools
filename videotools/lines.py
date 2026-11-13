"""A description table (training-video-tools' PLAN.md item 26): one Markdown table whose columns `#`, `Start (s)` and
`Line` are found by header, in any order; the rest ignored. Read for `narrate --lines`. An
optional `Say` column (training-video-tools' item 30) holds what is spoken instead of `Line`, with `[[…]]` spans.
"""

import re

from videotools import cli, phonemes

COLUMNS = ("#", "Start (s)", "Line")
SAY = "Say"


def cells(row):
    """The cells of a table row: split on `|` that is not escaped, `\\|` a pipe, each trimmed."""
    inner = row.strip()
    inner = inner.removeprefix("|")
    if inner.endswith("|") and not inner.endswith("\\|"):
        inner = inner[:-1]
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", inner)]


def read(path):
    """The lines of the table in the file at `path`; a missing or unreadable file is a Failure (exit 3)."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise cli.Failure(f"cannot read {path}: {e.strerror}") from None
    return parse(text, path)


def is_separator(row):
    """A Markdown table's second row: pipes, dashes, colons and spaces, with at least one dash."""
    return bool(re.fullmatch(r"[\s|:-]+", row)) and "-" in row


def parse(text, name):
    """The lines of the first table whose header has the three columns: [{"n", "start", "text"}, …],
    with "say" when the table has a `Say` column and the row's is not empty. Anything that cannot
    be spoken is a Failure in words (exit 3)."""
    rows = text.splitlines()
    header, first = None, None
    for i, row in enumerate(rows[:-1]):
        if row.lstrip().startswith("|") and is_separator(rows[i + 1]):
            header, first = cells(row), i + 2
            if all(c in header for c in COLUMNS):
                break
    if header is None:
        raise cli.Failure(f"{name} has no table with the columns '#', 'Start (s)' and 'Line'")
    missing = [c for c in COLUMNS if c not in header]
    if missing:
        raise cli.Failure("the table in {} has no {} column (its columns are {})".format(
            name, " or ".join(f"'{c}'" for c in missing), ", ".join(f"'{c}'" for c in header)))
    where = {c: header.index(c) for c in COLUMNS}
    out, seen = [], set()
    for k, line in enumerate(rows[first:], 1):
        if not line.lstrip().startswith("|"):
            break
        values = cells(line)
        row = f"row {k} of the table in {name}"
        if len(values) != len(header):
            raise cli.Failure(f"{row} has {len(values)} cells where the header has {len(header)}")
        number, start, text = (values[where[c]] for c in COLUMNS)
        if not re.fullmatch(r"[1-9][0-9]*", number):
            raise cli.Failure(f"{row}: '#' should be a whole number from 1, not '{number}'")
        if number in seen:
            raise cli.Failure(f"{row}: '#' {number} is given twice")
        seen.add(number)
        try:
            seconds = float(start)
        except ValueError:
            raise cli.Failure(f"{row}: 'Start (s)' should be seconds, not '{start}'") from None
        if seconds < 0:
            raise cli.Failure(f"{row}: 'Start (s)' cannot be negative ({start})")
        if not text:
            raise cli.Failure(f"{row}: 'Line' is empty")
        line = {"n": int(number), "start": seconds, "text": text}
        say = values[header.index(SAY)] if SAY in header else ""
        if say:
            wrong = phonemes.problems(say)
            if wrong:
                raise cli.Failure(f"{row}: '{SAY}': {wrong[0]}")
            line["say"] = say
        out.append(line)
    if not out:
        raise cli.Failure(f"the table in {name} has no rows")
    return out


WORDS_PER_SECOND = 2.6    # at speed 1, as narrate estimates a cue
SPEED_RANGE = (0.5, 2.0)  # what kokoro-onnx 0.6.1 accepts (training-video-tools' PLAN.md, "Things checked", 17 October 2026)


def clip_name(n, largest):
    """`01.wav`: at least two digits, more when the largest number needs them."""
    return f"{n:0{max(2, len(str(largest)))}d}.wav"


def overrun(spoken, i):
    """The warning when line i (of `spoken`: [(line, length), …] in table order) ends after the
    next line starts, or None."""
    if i + 1 >= len(spoken):
        return None
    (line, length), (after, _) = spoken[i], spoken[i + 1]
    over = line["start"] + length - after["start"]
    if over <= 0:
        return None
    return (f"line {line['n']} (at {line['start']:.2f} s, {length:.2f} s long) runs {over:.2f} s into "
            f"line {after['n']} (at {after['start']:.2f} s)")


def estimate(text, speed):
    return len(text.split()) / (WORDS_PER_SECOND * speed)


def check_speed(speed):
    low, high = SPEED_RANGE
    if not low <= speed <= high:
        raise cli.Failure(f"--speed should be from {low:.1f} to {high:.1f} (the model's range), not {speed:g}",
                          cli.USAGE)
    return speed
