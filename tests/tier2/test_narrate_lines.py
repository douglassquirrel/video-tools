"""narrate --lines (training-video-tools' item 26, taken in at fc6091a): each line of a description table to its own clip, with the stub
speech model; timing.json; the overrun warning; --dry-run; --replace; every refusal."""

import json
import os
import sys
from pathlib import Path

import pytest

from tests.tier2.conftest import run, run_program, stub_calls


def stub_length(words):
    """The stub's clip length after trimming: 0.03 + (0.5 + 0.25 W) + 0.08 seconds."""
    return round(0.03 + 0.5 + 0.25 * words + 0.08, 3)

TABLE = """# Harbour Dusk (invented)

| # | Start (s) | Words | Est. end (s) | Over | Checked against | Line |
|---|---|---|---|---|---|---|
| 1 | 0.10 | 6 | 1.30 | gap | stills 0.00 | A kite climbs over the harbour wall. |
| 2 | 4.00 | 5 | 5.00 | "Hi" | — | On screen: “Harbour”; it's dusk. |
| 3 | 9.50 | 3 | 10.10 |  | — | Gulls wheel \\| dip. |
"""


@pytest.fixture
def table(tmp_path):
    path = tmp_path / "vid" / "script.md"
    path.parent.mkdir()
    path.write_text(TABLE, encoding="utf-8")
    return path


def test_run_as_a_program_it_prints_and_writes_what_it_does_when_called_inside_the_test(table, speech, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    as_program = run_program("narrate", "--lines", table, "--out", a, "--speed", "1.5", env=speech)
    code, out, err = run("narrate", "--lines", table, "--out", b, "--speed", "1.5", env=speech)
    assert as_program[0] == 0 and "01.wav" in as_program[1]
    assert as_program == (code, out.replace(str(b), str(a)), err.replace(str(b), str(a)))
    assert sorted(os.listdir(a)) == sorted(os.listdir(b)) == ["01.wav", "02.wav", "03.wav", "timing.json"]
    assert [(a / n).read_bytes() for n in os.listdir(a)] == [(b / n).read_bytes() for n in os.listdir(a)]


def test_each_line_becomes_a_clip_named_by_its_number_with_timing_json(table, speech, tmp_path):
    out = tmp_path / "clips"
    code, stdout, err = run("narrate", "--lines", table, "--out", out, "--speed", "1.5", env=speech)
    assert (code, err) == (0, "")
    assert sorted(os.listdir(out)) == ["01.wav", "02.wav", "03.wav", "timing.json"]
    timing = json.loads((out / "timing.json").read_text())
    assert (timing["voice"], timing["speed"], timing["model"], timing["sample_rate"]) == ("bm_george", 1.5, "kokoro-82m", 24000)
    assert timing["lines"] == [
        {"n": 1, "start": 0.1, "text": "A kite climbs over the harbour wall.", "length": stub_length(7)},
        {"n": 2, "start": 4.0, "text": "On screen: “Harbour”; it's dusk.", "length": stub_length(5)},
        {"n": 3, "start": 9.5, "text": "Gulls wheel | dip.", "length": stub_length(3)},   # '|' is no word to the stub
    ]
    assert stdout.splitlines() == [f"01.wav  {stub_length(7):.3f} s", f"02.wav  {stub_length(5):.3f} s",
                                   f"03.wav  {stub_length(3):.3f} s", f"Wrote 3 clips and {out / 'timing.json'}"]
    creates = [c["create"] for c in stub_calls(speech) if "create" in c]
    assert [c["text"] for c in creates] == [", A KITE CLIMBS OVER THE HARBOUR WALL.", ", ON SCREEN: “HARBOUR”; IT'S DUSK.",
                                            ", GULLS WHEEL | DIP."]              # as phonemes with the lead-in (training-video-tools' item 30)
    assert {(c["voice"], c["speed"], c["lang"], c["is_phonemes"]) for c in creates} == {("bm_george", 1.5, "en-us", True)}


def test_dry_run_lists_the_lines_with_estimates_at_the_speed_and_writes_nothing(table, speech, tmp_path):
    out = tmp_path / "clips"
    code, stdout, err = run("narrate", "--lines", table, "--out", out, "--speed", "2", "--dry-run", env=speech)
    assert (code, err) == (0, "")
    assert stdout.splitlines() == [
        f"narrate (dry run): {table}",
        f"voice bm_george, speed 2.0, model kokoro-82m from {speech['SPEECH_MODEL_DIR_FOR_TESTS']}",
        "01.wav  at 0.10 s  ~1.3 s  A kite climbs over the harbour wall.",      # 7 words / (2.6 x 2)
        "02.wav  at 4.00 s  ~1.0 s  On screen: “Harbour”; it's dusk.",
        "03.wav  at 9.50 s  ~0.8 s  Gulls wheel | dip.",
        "3 lines, about 3 s of speech; nothing written (dry run).",
    ]
    assert not out.exists() and stub_calls(speech) == []


def test_a_line_that_runs_into_the_next_is_warned_about_on_stderr_and_the_run_still_succeeds(speech, tmp_path):
    path = tmp_path / "t.md"
    path.write_text("| # | Start (s) | Line |\n|---|---|---|\n| 1 | 0.10 | one two three four five six seven eight nine ten |\n"
                    "| 2 | 2.50 | short |\n| 3 | 9.00 | last |\n", encoding="utf-8")
    code, stdout, err = run("narrate", "--lines", path, "--out", tmp_path / "c", "--speed", "1", env=speech)
    assert code == 0
    assert err == "narrate: line 1 (at 0.10 s, 3.11 s long) runs 0.71 s into line 2 (at 2.50 s)\n"   # stub_length(10)
    assert stdout.splitlines()[0] == "01.wav  3.110 s"


def test_existing_clips_are_refused_and_replace_writes_over_them_listing_them_first(table, speech, tmp_path):
    out = tmp_path / "clips"
    out.mkdir()
    (out / "02.wav").write_bytes(b"mine")
    code, stdout, err = run("narrate", "--lines", table, "--out", out, "--speed", "1.5", env=speech)
    assert (code, stdout) == (3, "")
    assert err == f"narrate: these would be written over; delete them, or run with --replace:\n  {out / '02.wav'}\n"
    assert os.listdir(out) == ["02.wav"] and (out / "02.wav").read_bytes() == b"mine" and stub_calls(speech) == []
    code, stdout, err = run("narrate", "--lines", table, "--out", out, "--speed", "1.5", "--replace", env=speech)
    assert (code, err) == (0, "")
    assert stdout.splitlines()[:2] == ["Replacing:", f"  {out / '02.wav'}"]
    assert (out / "02.wav").read_bytes() != b"mine" and sorted(os.listdir(out)) == ["01.wav", "02.wav", "03.wav", "timing.json"]


SCRIPT_FORM = ("narrate here takes --lines TABLE.md --out FOLDER; the form that takes a training script "
               "(narrate SCRIPT.md) is training-video-tools'")


@pytest.mark.parametrize("args, message", [
    (["--lines", "T", "--out", "F", "--speed", "1", "S"], "S: " + SCRIPT_FORM),
    (["--lines", "T", "--out", "F", "--speed", "1", "--phonemes"],          # with --dry-run allowed since training-video-tools' item 30
     "--phonemes goes with --dry-run (it only shows what the voice would be given)"),
    (["--lines", "T", "--speed", "1"], "--lines needs --out FOLDER for the clips"),
    (["--lines", "T", "--out", "F", "--speed", "2.5"], "--speed should be from 0.5 to 2.0 (the model's range), not 2.5"),
    (["S", "--out", "F"], "S: " + SCRIPT_FORM),
    ([], "give --lines TABLE.md --out FOLDER"),
])
def test_the_script_form_and_bad_flags_are_refused_before_anything_is_read(table, speech, tmp_path, args, message):
    args = [table if a == "T" else tmp_path / "F" if a == "F" else tmp_path / "missing.md" if a == "S" else a for a in args]
    code, stdout, err = run("narrate", *args, env=speech)
    message = message.replace("S: ", f"{tmp_path / 'missing.md'}: ")
    assert (code, stdout, err) == (2, "", f"narrate: {message}\n")
    assert not (tmp_path / "F").exists() and stub_calls(speech) == []


def test_a_table_that_cannot_be_spoken_or_a_missing_file_is_refused_in_words(speech, tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("| # | Start (s) | Line |\n|---|---|---|\n| 1 | soon | Hi. |\n", encoding="utf-8")
    code, stdout, err = run("narrate", "--lines", bad, "--out", tmp_path / "c", "--speed", "1", env=speech)
    assert (code, stdout, err) == (3, "", f"narrate: row 1 of the table in {bad}: 'Start (s)' should be seconds, not 'soon'\n")
    code, stdout, err = run("narrate", "--lines", tmp_path / "none.md", "--out", tmp_path / "c", "--speed", "1", env=speech)
    assert (code, stdout, err) == (3, "", f"narrate: cannot read {tmp_path / 'none.md'}: No such file or directory\n")
    assert not (tmp_path / "c").exists() and stub_calls(speech) == []


def test_the_voice_flag_wins_and_without_a_config_voice_af_heart_is_the_default(table, speech, tmp_path):
    code, _stdout, err = run("narrate", "--lines", table, "--out", tmp_path / "a", "--voice", "zz_test", env=speech)
    assert code == 0
    timing = json.loads((tmp_path / "a" / "timing.json").read_text())
    assert (timing["voice"], timing["speed"]) == ("zz_test", 1.5)          # no --speed: 1.5 (Squirrel, 17 October 2026)
    creates = [c["create"] for c in stub_calls(speech) if "create" in c]
    assert {c["speed"] for c in creates} == {1.5}
    conf = tmp_path / "quiet.conf"
    conf.write_text(f"SPEECH_MODEL_DIR={speech['SPEECH_MODEL_DIR_FOR_TESTS']}\n")
    code, _stdout, err = run("narrate", "--lines", table, "--out", tmp_path / "b", "--speed", "1",
                            env={**speech, "VIDEO_TOOLS_CONF": str(conf)})
    assert code == 0 and json.loads((tmp_path / "b" / "timing.json").read_text())["voice"] == "af_heart"
    code, _stdout, err = run("narrate", "--lines", table, "--out", tmp_path / "c", "--speed", "1", "--voice", "nobody", env=speech)
    assert (code, err) == (3, "narrate: the model has no voice 'nobody' (it has af_heart, bm_george, zz_test)\n")


def test_a_model_failure_names_the_line_and_leaves_what_was_written(table, speech, tmp_path):
    out = tmp_path / "clips"
    code, stdout, err = run("narrate", "--lines", table, "--out", out, "--speed", "1", env={**speech, "KOKORO_STUB_FAIL": "1"})
    assert (code, stdout) == (4, "")
    assert err == "narrate: the speech model failed on line 1 (stub: the model failed on purpose); nothing written for it\n"
    assert os.listdir(out) == []


SAY_TABLE = """| # | Start (s) | Line | Say |
|---|---|---|---|
| 1 | 0.10 | Silas smiles. | [[sˈɪləs]] smiles. |
| 2 | 2.00 | Thea nods. |  |
| 3 | 4.00 | Hugo sits. | Hugo sits, slowly. |
"""


@pytest.fixture
def say_table(tmp_path):
    path = tmp_path / "say.md"
    path.write_text(SAY_TABLE, encoding="utf-8")
    return path


def test_a_row_with_say_is_spoken_from_it_spans_as_phonemes_and_timing_keeps_the_line(say_table, speech, tmp_path):
    out = tmp_path / "clips"
    code, _stdout, err = run("narrate", "--lines", say_table, "--out", out, "--speed", "1.5", env=speech)
    assert (code, err) == (0, "")
    creates = [c["create"] for c in stub_calls(speech) if "create" in c]
    assert [(c["text"], c["is_phonemes"], c["lang"]) for c in creates] == [
        (", ssˈɪləs SMILES.", True, "en-us"),       # the stub's phonemizer upper-cases the text part; the lead-in
        (", THEA NODS.", True, "en-us"),            # an empty Say: the Line
        (", HUGO SITS, SLOWLY.", True, "en-us"),    # a Say with no span
    ]
    timing = json.loads((out / "timing.json").read_text())
    assert [(x["n"], x["text"], x["length"]) for x in timing["lines"]] == [
        (1, "Silas smiles.", stub_length(2)), (2, "Thea nods.", stub_length(2)), (3, "Hugo sits.", stub_length(3))]


def test_dry_run_shows_each_say_and_estimates_from_what_is_spoken(say_table, speech, tmp_path):
    code, stdout, err = run("narrate", "--lines", say_table, "--out", tmp_path / "c", "--speed", "1", "--dry-run", env=speech)
    assert (code, err) == (0, "")
    assert stdout.splitlines()[2:] == [
        "01.wav  at 0.10 s  ~0.8 s  Silas smiles.",
        "    say: [[sˈɪləs]] smiles.",
        "02.wav  at 2.00 s  ~0.8 s  Thea nods.",
        "03.wav  at 4.00 s  ~1.2 s  Hugo sits.",                # 3 words of the Say / 2.6
        "    say: Hugo sits, slowly.",
        "3 lines, about 3 s of speech; nothing written (dry run).",
    ]
    assert stub_calls(speech) == []


def test_dry_run_with_phonemes_prints_each_lines_phonemes_spans_spliced_and_writes_nothing(say_table, speech, tmp_path):
    code, stdout, err = run("narrate", "--lines", say_table, "--out", tmp_path / "c", "--speed", "1", "--dry-run", "--phonemes",
                            env=speech)
    assert (code, err) == (0, "")
    assert stdout.splitlines()[2:-1] == [
        "01.wav  at 0.10 s  ~0.8 s  Silas smiles.",
        "    say: [[sˈɪləs]] smiles.",
        "    phonemes: , ssˈɪləs SMILES.",
        "02.wav  at 2.00 s  ~0.8 s  Thea nods.",
        "    phonemes: , THEA NODS.",
        "03.wav  at 4.00 s  ~1.2 s  Hugo sits.",
        "    say: Hugo sits, slowly.",
        "    phonemes: , HUGO SITS, SLOWLY.",
    ]
    assert not (tmp_path / "c").exists()
    assert [c for c in stub_calls(speech) if "create" in c or "init" in c] == []   # the tokenizer only, no model


def test_a_say_with_a_wrong_span_is_refused_before_the_model_is_loaded(speech, tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("| # | Start (s) | Line | Say |\n|---|---|---|---|\n| 1 | 0 | Silas smiles. | [[sˈɪləs smiles. |\n",
                   encoding="utf-8")
    code, stdout, err = run("narrate", "--lines", bad, "--out", tmp_path / "c", "--speed", "1", env=speech)
    assert (code, stdout) == (3, "")
    assert err == f"narrate: row 1 of the table in {bad}: 'Say': '[[' at character 1 is never closed with ']]'\n"
    assert not (tmp_path / "c").exists() and stub_calls(speech) == []


def test_help_names_the_optional_say_column_and_phonemes_for_a_line(speech):
    code, stdout, _err = run("narrate", "--help", env=speech)
    text = " ".join(stdout.split())
    assert code == 0
    assert "('#', 'Start (s)', 'Line', and optionally 'Say', spoken instead of 'Line', [[…]] spans allowed)" in text
    assert "--phonemes with --dry-run: also print the phoneme string each cue or line would be given" in text


# The paths --lines shares with training-video-tools' script form, whose tests stayed there: taken
# in here for --lines.

def test_help_names_every_flag_and_the_settings_file():
    code, out, err = run("narrate", "--help")
    assert code == 0 and err == ""
    assert " ".join(out.split()).startswith("usage: narrate [-h] [--lines TABLE.md] [--out FOLDER] [--voice VOICE] [--speed SPEED] "
                          "[--replace] [--phonemes] [--dry-run]")
    assert "~/.video-tools.conf" in " ".join(out.split()) and "--scenes" not in out


@pytest.mark.parametrize("args", [["--scenes", "A"], ["--speed"], ["--speed", "fast"]])
def test_a_flag_it_does_not_have_or_without_a_value_is_usage(table, tmp_path, args):
    code, out, err = run("narrate", "--lines", table, "--out", tmp_path / "c", *args)
    assert (code, out) == (2, "") and err.startswith("usage: narrate") and "Traceback" not in err
    assert not (tmp_path / "c").exists()


def test_the_clips_are_real_wav_files_of_the_recorded_length(table, speech, tmp_path):
    import soundfile
    assert run("narrate", "--lines", table, "--out", tmp_path / "c", env=speech)[0] == 0
    info = soundfile.info(str(tmp_path / "c" / "01.wav"))
    assert (info.samplerate, info.channels) == (24000, 1)
    assert round(info.frames / info.samplerate, 3) == stub_length(7)


def test_a_missing_model_folder_is_refused_naming_the_setting(table, speech, tmp_path):
    conf = tmp_path / "other.conf"
    conf.write_text("SPEECH_MODEL_DIR=%s\n" % (tmp_path / "nowhere"))
    code, out, err = run("narrate", "--lines", table, "--out", tmp_path / "c", env=dict(speech, VIDEO_TOOLS_CONF=str(conf)))
    assert (code, out) == (3, "")
    assert err == ("narrate: no model.onnx and voices.npz in {} (SPEECH_MODEL_DIR in {}); "
                   "see the README's one-time set-up\n".format(tmp_path / "nowhere", conf))
    assert not (tmp_path / "c").exists()


def test_a_config_without_the_model_setting_or_with_a_bad_line_is_refused(table, speech, tmp_path):
    conf = tmp_path / "other.conf"
    conf.write_text("VOICE=af_heart\n")
    code, out, err = run("narrate", "--lines", table, "--out", tmp_path / "c", env=dict(speech, VIDEO_TOOLS_CONF=str(conf)))
    assert (code, out) == (3, "")
    assert err == f"narrate: SPEECH_MODEL_DIR is not set in {conf}; see the README's one-time set-up\n"
    conf.write_text("SPEED=1.0\n")
    code, out, err = run("narrate", "--lines", table, "--out", tmp_path / "c", env=dict(speech, VIDEO_TOOLS_CONF=str(conf)))
    assert (code, out) == (3, "")
    assert err == f"narrate: {conf}: line 1: unknown setting 'SPEED' (the settings are SPEECH_MODEL_DIR, VOICE)\n"


def test_a_missing_speech_package_is_a_useful_error_exit_4_for_a_run_and_for_phonemes(table, speech, tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "kokoro_onnx.py").write_text("raise ImportError(\"No module named 'kokoro_onnx'\")\n")
    for extra in ([], ["--dry-run", "--phonemes"]):
        code, out, err = run("narrate", "--lines", table, "--out", tmp_path / "c", *extra,
                             env=dict(speech, PYTHONPATH=str(broken)))
        assert (code, out) == (4, "")
        assert err.startswith(f"narrate: the Python package 'kokoro-onnx' is not installed in this Python ({sys.executable}); "
                              'install it with .venv/bin/pip install "kokoro-onnx==0.6.1"')
    assert not (tmp_path / "c").exists()


def test_the_table_and_the_config_are_never_modified(table, speech, tmp_path):
    conf = speech["VIDEO_TOOLS_CONF"]
    before = (Path(table).read_bytes(), Path(conf).read_bytes())
    assert run("narrate", "--lines", table, "--out", tmp_path / "c", env=speech)[0] == 0
    assert (Path(table).read_bytes(), Path(conf).read_bytes()) == before


def test_timing_json_keeps_non_ascii_text_as_written(table, speech, tmp_path):
    assert run("narrate", "--lines", table, "--out", tmp_path / "c", env=speech)[0] == 0
    text = (tmp_path / "c" / "timing.json").read_text(encoding="utf-8")
    assert "“Harbour”" in text and "\\u201c" not in text
