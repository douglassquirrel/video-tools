"""videotools.config: ~/.video-tools.conf, read and never run (taken in from training-video-tools)."""

import re

import pytest

from videotools import config


def test_keys_values_comments_quotes_and_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    conf = tmp_path / "video-tools.conf"
    conf.write_text('# a comment\nSPEECH_MODEL_DIR=~/models/kokoro   # trailing comment\n\nVOICE = "af_heart"\n')
    assert config.read(str(conf)) == {"SPEECH_MODEL_DIR": str(tmp_path / "models" / "kokoro"), "VOICE": "af_heart"}


def test_a_single_quoted_value_loses_its_quotes(tmp_path):
    conf = tmp_path / "c.conf"
    conf.write_text("VOICE='bm george'\n")
    assert config.read(str(conf)) == {"VOICE": "bm george"}


def test_a_missing_file_is_an_empty_config(tmp_path):
    assert config.read(str(tmp_path / "none.conf")) == {}


def test_an_unknown_key_or_a_line_without_equals_is_refused_naming_its_line(tmp_path):
    conf = tmp_path / "c.conf"
    conf.write_text("VOICE=af_heart\nVOICES=x\njust words\n")
    with pytest.raises(config.ConfigError) as e:
        config.read(str(conf))
    assert str(e.value) == (f"{conf}: line 2: unknown setting 'VOICES' (the settings are SPEECH_MODEL_DIR, VOICE)\n"
                            f"{conf}: line 3: not KEY=value: just words")


def test_training_video_tools_settings_are_not_settings_here(tmp_path):
    conf = tmp_path / "c.conf"
    conf.write_text("SPEED=1.0\n")
    with pytest.raises(config.ConfigError) as e:
        config.read(str(conf))
    assert str(e.value) == f"{conf}: line 1: unknown setting 'SPEED' (the settings are SPEECH_MODEL_DIR, VOICE)"


def test_the_default_path_is_in_home_unless_the_environment_names_another(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VIDEO_TOOLS_CONF", raising=False)
    assert config.path() == str(tmp_path / ".video-tools.conf")
    monkeypatch.setenv("VIDEO_TOOLS_CONF", str(tmp_path / "other.conf"))
    assert config.path() == str(tmp_path / "other.conf")
    (tmp_path / "other.conf").write_text("VOICE=bm_george\n")
    assert config.read() == {"VOICE": "bm_george"}


def test_training_video_tools_own_file_and_variable_are_not_read(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VIDEO_TOOLS_CONF", raising=False)
    monkeypatch.setenv("TRAINING_VIDEO_TOOLS_CONF", str(tmp_path / "theirs.conf"))
    (tmp_path / "theirs.conf").write_text("VOICE=af_heart\n")
    (tmp_path / ".training-video-tools.conf").write_text("VOICE=af_heart\n")
    assert config.path() == str(tmp_path / ".video-tools.conf")
    assert config.read() == {}


def test_the_example_settings_file_is_named_for_the_project_and_sets_every_setting_once_uncommented(tmp_path,
                                                                                                    monkeypatch):
    import os
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = os.path.join(os.path.dirname(__file__), "..", "..")
    with open(os.path.join(repo, "video-tools.conf.example"), encoding="utf-8") as f:
        text = f.read()
    assert text.startswith("# Copy to ~/.video-tools.conf and edit.")
    conf = tmp_path / "c.conf"
    conf.write_text(re.sub(r"(?m)^#(?=[A-Z_]+=)", "", text))
    assert sorted(config.read(str(conf))) == sorted(config.KEYS)
