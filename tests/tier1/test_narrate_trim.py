"""videotools.narrate.trim: silence cut to 30 ms before the first and 80 ms after the last sound."""

import numpy as np

from videotools import narrate

RATE = 1000


def test_silence_at_both_ends_is_trimmed_leaving_the_margins():
    samples = np.concatenate([np.zeros(500), np.full(200, 0.3), np.zeros(400)]).astype(np.float32)
    out = narrate.trim(samples, RATE)
    assert len(out) == 30 + 200 + 80
    assert out[30] == np.float32(0.3) and out[29] == 0


def test_a_clip_with_sound_at_the_very_start_keeps_what_there_is():
    samples = np.full(100, 0.2, np.float32)
    assert len(narrate.trim(samples, RATE)) == 100


def test_a_margin_shorter_than_the_silence_is_kept_whole():
    samples = np.concatenate([np.zeros(10), np.full(50, 0.2), np.zeros(20)]).astype(np.float32)
    assert len(narrate.trim(samples, RATE)) == 10 + 50 + 20


def test_a_clip_that_is_all_silence_is_left_as_it_is():
    samples = np.zeros(300, np.float32)
    assert len(narrate.trim(samples, RATE)) == 300


def test_samples_at_exactly_the_threshold_count_as_silence():
    samples = np.concatenate([np.full(100, 0.01), np.full(10, 0.5), np.full(100, 0.01)]).astype(np.float32)
    assert len(narrate.trim(samples, RATE)) == 30 + 10 + 80
