"""Where a cut falls, and what the cut transcript holds. Times are whole milliseconds."""

from dataclasses import dataclass

from videotools.match import find_phrase
from videotools.srt import Cue


@dataclass
class Cut:
    start: int
    end: int
    first: int
    last: int


class CutError(Exception):
    """A cut that cannot be made; `code` is the command's exit code for it."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def clock(ms):
    """Milliseconds as HH:MM:SS.mmm, for people to read."""
    s, ms = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _only(cues, flag, phrase):
    """The one place `phrase` is found, or a CutError."""
    found = find_phrase(cues, phrase)
    if not found:
        raise CutError(5, f'the {flag} phrase "{phrase}" is not in the transcript')
    if len(found) > 1:
        times = [clock(cues[begin].start) for begin, _ in found]
        raise CutError(6, 'the {} phrase "{}" is found {} times, at {} and {}: give a longer phrase, found only '
                          'once'.format(flag, phrase, len(found), ", ".join(times[:-1]), times[-1]))
    return found[0]


def locate(cues, from_phrase, to_phrase, length):
    """The cut from the cue where `from_phrase` begins to the cue where `to_phrase` ends, in a video `length` long.
    A phrase that is None leaves that end of the video where it is."""
    first, start = 0, 0
    if from_phrase is not None:
        first = _only(cues, "--from", from_phrase)[0]
        start = cues[first].start
        if start >= length:
            raise CutError(7, f"the --from phrase begins at {clock(start)}, after the video ends at {clock(length)}")
    last, end = len(cues) - 1, length
    if to_phrase is not None:
        last = _only(cues, "--to", to_phrase)[1]
        end = min(cues[last].end, length)
        if last < first or end <= start:
            raise CutError(7, f"the --to phrase ends at {clock(end)}, not after the --from phrase begins at {clock(start)}")
    return Cut(start, end, first, last)



def cut_cues(cues, cut):
    """The cues from the first to the last of the cut, moved back by its start and kept inside it."""
    def inside(ms):
        return min(max(ms - cut.start, 0), cut.end - cut.start)
    return [Cue(inside(c.start), inside(c.end), list(c.lines)) for c in cues[cut.first:cut.last + 1]]


def plain_text(cues):
    """The cues as plain text, one cue per line, its lines joined by a space, no times."""
    return "".join(" ".join(c.lines) + "\n" for c in cues)


def seconds(ms):
    return "{}.{:03d}".format(*divmod(ms, 1000))


def ffmpeg_args(video, cut, out):
    """The ffmpeg command that writes the cut of `video` to `out` (an mp4, whatever its name), re-encoded so the
    cut is exact, with only the first video and the first audio stream."""
    return ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", seconds(cut.start), "-i", video, "-t", seconds(cut.end - cut.start),
            "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart",
            "-f", "mp4", out]
