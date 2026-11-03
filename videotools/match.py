"""Finding a phrase in a transcript's cues.

Text is compared as a list of words: case folded, NFC and NFD made alike, apostrophes dropped (so "don't",
"don’t" and "dont" are one word), and everything else that is not a letter or a digit taken as a break between
words. A phrase matches a run of whole words, which may cross from one cue into the next.
"""

import re
import unicodedata

WORD = re.compile(r"[^\W_]+")
APOSTROPHES = re.compile("['\u2019\u02bc]")


def words(text):
    """The words of `text`, as compared."""
    folded = unicodedata.normalize("NFC", unicodedata.normalize("NFC", text).casefold())
    return WORD.findall(APOSTROPHES.sub("", folded))


def find_phrase(cues, phrase):
    """Every place `phrase` is found, as (index of the cue it begins in, index of the cue it ends in)."""
    wanted = words(phrase)
    found = [(w, i) for i, cue in enumerate(cues) for line in cue.lines for w in words(line)]
    text = [w for w, _ in found]
    n = len(wanted)
    return [(found[k][1], found[k + n - 1][1])
            for k in range(len(text) - n + 1) if text[k:k + n] == wanted]
