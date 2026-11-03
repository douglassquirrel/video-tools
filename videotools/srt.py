"""Reading and writing SubRip (.srt) transcripts. Times are whole milliseconds."""

import re
from dataclasses import dataclass


@dataclass
class Cue:
    start: int
    end: int
    lines: list[str]


class SrtError(Exception):
    """A malformed transcript; `line` is the 1-based line it was found on."""

    def __init__(self, line, message):
        super().__init__(message)
        self.line = line
        self.message = message


TIMES = re.compile(r"^(\d+):(\d\d):(\d\d)[,.](\d\d\d) --> (\d+):(\d\d):(\d\d)[,.](\d\d\d)$")


def _ms(line, h, m, s, ms):
    if int(m) >= 60 or int(s) >= 60:
        raise SrtError(line, "the seconds or minutes are 60 or more")
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def parse_srt(text):
    """The cues of an .srt file's text, in order. Raises SrtError naming the line of a fault."""
    cues = []
    lines = [line.rstrip("\r") for line in text.lstrip("\ufeff").split("\n")]
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if not lines[i].strip().isdigit():
            raise SrtError(i + 1, f"expected a cue number, found {lines[i].strip()!r}")
        if not any(line.strip() for line in lines[i + 1:]):
            raise SrtError(i + 1, "the transcript ends after a cue number, with no times")
        times = TIMES.match(lines[i + 1].strip())
        if not times:
            raise SrtError(i + 2, "expected the cue's times as 00:00:00,000 --> 00:00:00,000, "
                                  f"found {lines[i + 1].strip()!r}")
        start, end = _ms(i + 2, *times.group(1, 2, 3, 4)), _ms(i + 2, *times.group(5, 6, 7, 8))
        if end < start:
            raise SrtError(i + 2, "the cue ends before it starts")
        i += 2
        body = []
        while i < len(lines) and lines[i].strip():
            body.append(lines[i])
            i += 1
        cues.append(Cue(start, end, body))
    return cues


def srt_time(ms):
    """Milliseconds as an .srt time, HH:MM:SS,mmm."""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_srt(cues):
    """The text of an .srt file holding `cues`, numbered from 1."""
    return "".join(
        "{}\n{} --> {}\n{}\n\n".format(n, srt_time(c.start), srt_time(c.end), "\n".join(c.lines))
        for n, c in enumerate(cues, 1))
