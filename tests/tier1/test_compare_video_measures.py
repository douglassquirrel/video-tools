"""compare-video: the envelope, its correlation, the speech/silence disagreements and the
frame-difference summary, on hand-written numbers."""

import numpy as np

from videotools import compare_video


def test_the_envelope_is_the_rms_of_each_window_dropping_a_partial_last_window():
    rate, window = 10, 0.5                       # 5 samples a window
    samples = np.array([0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 1, 1], dtype=np.int16)
    env = compare_video.envelope(samples, rate, window)
    assert env.tolist() == [0.0, 3.0]            # the two samples left over are dropped


def test_correlation_is_pearsons_over_the_shorter_envelope_and_undefined_when_one_is_flat():
    a = np.array([0.0, 1.0, 0.0, 1.0, 0.0])
    b = np.array([0.0, 1.0, 0.0, 1.0])
    assert compare_video.correlation(a, b) == 1.0
    assert round(compare_video.correlation(a, 1.0 - b), 4) == -1.0
    assert compare_video.correlation(a, np.array([0.5, 0.5, 0.5])) is None


def test_disagreements_count_windows_that_are_speech_in_one_and_silence_in_the_other():
    loud, quiet = 3276.7, 10.0                   # -20 dBFS and -70 dBFS of a 16-bit full scale
    a = np.array([loud, loud, quiet, quiet, loud])
    b = np.array([loud, quiet, quiet, loud, loud, loud])
    assert compare_video.disagreements(a, b) == (2, 5)   # windows 1 and 3, of the 5 compared


def test_speech_is_above_minus_40_dbfs_of_a_16_bit_full_scale():
    assert compare_video.is_speech(np.array([328.0, 327.0])).tolist() == [True, False]   # the line is 327.68


def test_the_summary_gives_the_mean_median_and_five_largest_with_ties_by_time():
    diffs = [(0.0, 0.0), (5.0, 151.7), (10.0, 161.7), (15.0, 161.7), (20.0, 0.0), (25.0, 151.7), (30.0, 0.0)]
    mean, median, largest = compare_video.summarise(diffs)
    assert round(mean, 2) == 89.54 and median == 151.7
    assert largest == [(10.0, 161.7), (15.0, 161.7), (5.0, 151.7), (25.0, 151.7), (0.0, 0.0)]


def test_the_envelope_is_the_root_mean_square_not_the_mean_of_the_magnitudes():
    samples = np.array([0, 4, 0, 4], dtype=np.int16)
    assert compare_video.envelope(samples, 4, 1.0).tolist() == [8 ** 0.5]   # the mean of the magnitudes is 2
