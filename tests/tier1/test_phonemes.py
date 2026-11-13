"""videotools.phonemes: [[…]] spans in a say: line, and what is wrong with them."""

import pytest

from videotools import phonemes


def test_a_line_splits_into_text_parts_and_spans_keeping_the_spaces_as_written():
    assert phonemes.parts("Say [[kɑːɹpˈæθi]] here") == [("Say ", False), ("kɑːɹpˈæθi", True), (" here", False)]
    assert phonemes.parts("[[a]][[b]] c") == [("a", True), ("b", True), (" c", False)]
    assert phonemes.parts("plain words") == [("plain words", False)]
    assert phonemes.parts("") == []
    assert phonemes.has_span("x [[y]]") is True and phonemes.has_span("x [y]") is False


def test_an_unclosed_empty_or_unopened_span_is_a_problem():
    assert phonemes.problems("accept [[ɐksˈɛptɔːl") == ["'[[' at character 8 is never closed with ']]'"]
    assert phonemes.problems("accept [[]] all") == ["'[[]]' at character 8 is empty"]
    assert phonemes.problems("accept ]] all") == ["']]' at character 8 has no '[[' before it"]
    assert phonemes.problems("[[a]] and [[") == ["'[[' at character 11 is never closed with ']]'"]


def test_a_symbol_the_voice_would_drop_is_a_problem_with_its_code_point_once_per_symbol():
    assert phonemes.problems("[[kɑːɹpˈæθi]]") == []
    assert phonemes.problems("[[kɑ ɹp]]") == []                     # a space is in the vocabulary
    assert phonemes.problems("[[kar$path$y]]") == ["'$' (U+0024) in '[[kar$path$y]]' is not a symbol the voice knows"]
    assert phonemes.problems("[[x]] [[é]]") == ["'é' (U+00E9) in '[[é]]' is not a symbol the voice knows"]


def test_the_vocabulary_is_the_114_symbols_of_kokoro_onnx_0_6_1():
    assert len(phonemes.VOCAB) == 114 and len(set(phonemes.VOCAB)) == 114
    assert all(c in phonemes.VOCAB for c in " ˈˌːɑæθɹ.,;:!?")
    assert "[" not in phonemes.VOCAB and "]" not in phonemes.VOCAB


def test_splicing_keeps_the_spaces_beside_a_span_even_though_the_phonemizer_strips_them():
    strip_and_upper = lambda text: text.strip().upper()     # noqa: E731  as the model's phonemize() does
    assert phonemes.splice("Say [[kɑːɹpˈæθi]] here", strip_and_upper) == "SAY kɑːɹpˈæθi HERE"
    assert phonemes.splice("[[a]][[b]] c", strip_and_upper) == "ab C"
    assert phonemes.splice("plain words ", strip_and_upper) == "PLAIN WORDS"


@pytest.mark.parametrize("given, expected", [
    ("sˈaɪləs smˈaɪlz.", ", ssˈaɪləs smˈaɪlz."),          # a quiet first consonant doubled
    ("fɪˈoʊnə wˈeɪts.", ", ffɪˈoʊnə wˈeɪts."),
    ("θˈiə nˈɑːdz.", ", θθˈiə nˈɑːdz."),
    ("ʃˈoʊnə wˈeɪvz.", ", ʃʃˈoʊnə wˈeɪvz."),
    ("hjˈuːɡoʊ sˈɪts.", ", hhjˈuːɡoʊ sˈɪts."),
    ("bɹˈæm wˈeɪvz.", ", bɹˈæm wˈeɪvz."),                # a loud one only the comma
    ("ɐ kˈaɪt klˈaɪmz.", ", ɐ kˈaɪt klˈaɪmz."),          # a vowel only the comma
    ("ðˈɛn sˈaɪləs.", ", ðˈɛn sˈaɪləs."),                 # voiced: not doubled
    ("  sˈæm.", ", ssˈæm."),                              # leading spaces dropped
    ("", ""),                                             # nothing to say stays nothing
])
def test_the_lead_in_puts_a_comma_first_and_doubles_a_quiet_first_consonant(given, expected):
    assert phonemes.lead_in(given) == expected
