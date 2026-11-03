"""Tier 1: finding a phrase in a transcript's cues."""

import unicodedata

from videotools.match import find_phrase
from videotools.srt import Cue


def cues(*texts):
    return [Cue(i * 1000, i * 1000 + 1000, [t]) for i, t in enumerate(texts)]


def test_finds_the_cue_where_a_phrase_begins_and_the_cue_where_it_ends():
    assert find_phrase(cues("Hello.", "Welcome to the show.", "Bye."), "welcome to the show") == [(1, 1)]


def test_ignores_case_punctuation_and_runs_of_white_space():
    assert find_phrase(cues("So -- WELCOME,   to\tthe   show!"), "welcome to the... show") == [(0, 0)]


def test_treats_nfc_and_nfd_alike():
    nfd = unicodedata.normalize("NFD", "Café crème")
    nfc = unicodedata.normalize("NFC", "café CRÈME")
    assert find_phrase(cues(nfd), nfc) == [(0, 0)]
    assert find_phrase(cues(nfc), nfd) == [(0, 0)]


def test_an_apostrophe_is_not_a_break_between_words():
    assert find_phrase(cues("We don’t stop."), "we don't stop") == [(0, 0)]
    assert find_phrase(cues("We don't stop."), "we dont stop") == [(0, 0)]


def test_a_phrase_may_run_across_cues_and_their_lines():
    found = find_phrase([Cue(0, 1, ["and that is", "the end"]), Cue(1, 2, ["of the"]), Cue(2, 3, ["show today"])],
                        "the end of the show")
    assert found == [(0, 2)]


def test_matches_whole_words_only():
    assert find_phrase(cues("And soon we start."), "and so") == []
    assert find_phrase(cues("And so we start."), "and so") == [(0, 0)]


def test_gives_every_place_a_phrase_is_found():
    assert find_phrase(cues("Thank you.", "Right.", "Thank you", "very much."), "thank you") == [(0, 0), (2, 2)]


def test_finds_nothing_when_the_phrase_is_not_there():
    assert find_phrase(cues("Hello."), "goodbye") == []
