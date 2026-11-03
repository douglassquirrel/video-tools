"""Tier 2: cut-video against stubs of ffmpeg and ffprobe."""

import os

from tests.tier2.conftest import digest, run_cut_video, run_script


def test_help_shows_the_usage_and_every_flag(stubs):
    code, out, _err = run_script("--help", env=dict(os.environ))
    assert code == 0
    assert out.startswith("usage: cut-video [-h] [--dry-run] [--from PHRASE] [--to PHRASE] --out DIR")
    for flag in ("--dry-run", "--from PHRASE", "--to PHRASE", "--out DIR", "VIDEO", "TRANSCRIPT"):
        assert flag in out


def test_writes_the_cut_video_transcript_and_text_and_nothing_else(stubs, inputs, tmp_path, capsys):
    video, srt = inputs
    out = tmp_path / "out"
    before = (digest(video), digest(srt))
    code = run_cut_video("--from", "welcome to", "--to", "thank you", "--out", out, video, srt)
    o, e = capsys.readouterr()
    assert (code, e) == (0, "")
    assert sorted(os.listdir(out)) == ["talk-cut.mp4", "talk-cut.srt", "talk-cut.txt"]
    assert (out / "talk-cut.mp4").read_bytes() == b"stub mp4"
    assert (out / "talk-cut.srt").read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:05,500\nWelcome to the show.\n\n"
        "2\n00:00:05,500 --> 00:00:11,000\nToday, cutting video.\n\n"
        "3\n00:00:11,000 --> 00:00:17,000\nThat's all,\nthank you.\n\n")
    assert (out / "talk-cut.txt").read_text(encoding="utf-8") == (
        "Welcome to the show.\nToday, cutting video.\nThat's all, thank you.\n")
    assert o == ("Cut 00:00:04.000 to 00:00:21.000 (00:00:17.000 long), 3 cues.\n"
                 f"Wrote {out}/talk-cut.mp4\nWrote {out}/talk-cut.srt\nWrote {out}/talk-cut.txt\n")
    assert (digest(video), digest(srt)) == before
    probe, = stubs.calls("ffprobe")
    assert probe == ["-v", "error", "-show_entries", "format=duration", "-of",
                     "default=noprint_wrappers=1:nokey=1", str(video)]
    ffmpeg, = stubs.calls("ffmpeg")
    assert ffmpeg[:12] == ["-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                           "-ss", "4.000", "-i", str(video), "-t", "17.000", "-map"]
    assert os.path.dirname(ffmpeg[-1]) == str(out) and ffmpeg[-1] != str(out / "talk-cut.mp4")


def test_file_names_and_phrases_are_handed_over_as_data(stubs, tmp_path, capsys):
    folder = tmp_path / "it's \"$HOME\" \\ – né\nline"
    folder.mkdir()
    video = folder / "-ta`lk $(x).mov"
    video.write_bytes(b"v")
    srt = folder / "t.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nSay \"$HOME\" </script> \\ né’s.\n", encoding="utf-8")
    code = run_cut_video("--from", "say \"$home\" </script> \\ nés", "--out", folder / "out", video, srt)
    capsys.readouterr()
    assert code == 0
    ffmpeg, = stubs.calls("ffmpeg")
    assert ffmpeg[ffmpeg.index("-i") + 1] == str(video)
    assert sorted(os.listdir(folder / "out")) == ["-ta`lk $(x)-cut.mp4", "-ta`lk $(x)-cut.srt", "-ta`lk $(x)-cut.txt"]


def test_runs_from_any_working_folder_with_relative_paths(stubs, inputs, tmp_path):
    video, srt = inputs
    code, _out, err = run_script("--to", "cutting video", "--out", "out", "in/" + video.name, "in/" + srt.name,
                                cwd=tmp_path, env=dict(os.environ))
    assert (code, err) == (0, "")
    assert sorted(os.listdir(tmp_path / "out")) == ["talk-cut.mp4", "talk-cut.srt", "talk-cut.txt"]


def refusal(capsys, *args):
    code = run_cut_video(*args)
    o, e = capsys.readouterr()
    return code, o, e


def test_refuses_to_run_with_neither_from_nor_to(stubs, inputs, tmp_path, capsys):
    code, _o, e = refusal(capsys, "--out", tmp_path / "out", *inputs)
    assert code == 2
    assert e.endswith("cut-video: error: give --from PHRASE, --to PHRASE or both: with neither there is "
                      "nothing to cut\n")
    assert not (tmp_path / "out").exists() and stubs.calls() == []


def test_refuses_a_phrase_with_no_words(stubs, inputs, tmp_path, capsys):
    code, _o, e = refusal(capsys, "--to", " ... ", "--out", tmp_path / "out", *inputs)
    assert code == 2
    assert e.endswith('cut-video: error: the --to phrase " ... " has no words to look for\n')


def test_refuses_a_missing_video(stubs, inputs, tmp_path, capsys):
    _video, srt = inputs
    code, o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", tmp_path / "nope.mov", srt)
    assert (code, o) == (3, "")
    assert e == "cut-video: cannot read the video {}: no such file or directory. Check the path.\n".format(
        tmp_path / "nope.mov")
    assert not (tmp_path / "out").exists() and stubs.calls() == []


def test_refuses_a_video_that_is_a_folder(stubs, inputs, tmp_path, capsys):
    _video, srt = inputs
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", tmp_path, srt)
    assert (code, e) == (3, f"cut-video: cannot read the video {tmp_path}: is a directory. Check the path.\n")


def test_refuses_a_missing_transcript(stubs, inputs, tmp_path, capsys):
    video, _srt = inputs
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", video, tmp_path / "nope.srt")
    assert (code, e) == (3, "cut-video: cannot read the transcript {}: no such file or directory. "
                            "Check the path.\n".format(tmp_path / "nope.srt"))


def test_refuses_a_transcript_that_is_not_utf8(stubs, inputs, tmp_path, capsys):
    video, srt = inputs
    srt.write_bytes("1\n00:00:01,000 --> 00:00:02,000\nCafé\n".encode("latin-1"))
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", video, srt)
    assert (code, e) == (3, (f"cut-video: the transcript {srt} is not UTF-8 text. Save it as UTF-8 and try "
                            "again.\n"))


def test_refuses_a_malformed_transcript_naming_the_line(stubs, inputs, tmp_path, capsys):
    video, srt = inputs
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nHi.\n\n2\nsoon\nBye.\n", encoding="utf-8")
    code, _o, e = refusal(capsys, "--from", "hi", "--out", tmp_path / "out", video, srt)
    assert (code, e) == (4, (f"cut-video: the transcript {srt} is not a SubRip (.srt) file I can read: line 6: "
                            "expected the cue's times as 00:00:00,000 --> 00:00:00,000, found 'soon'\n"))
    assert not (tmp_path / "out").exists() and stubs.calls() == []


def test_refuses_a_transcript_with_no_cues(stubs, inputs, tmp_path, capsys):
    video, srt = inputs
    srt.write_text("\n\n", encoding="utf-8")
    code, _o, e = refusal(capsys, "--from", "hi", "--out", tmp_path / "out", video, srt)
    assert (code, e) == (4, (f"cut-video: the transcript {srt} holds no cues, so there is nothing to find a phrase "
                            "in.\n"))


def test_refuses_a_phrase_not_found(stubs, inputs, tmp_path, capsys):
    code, o, e = refusal(capsys, "--from", "goodbye", "--out", tmp_path / "out", *inputs)
    assert (code, o, e) == (5, "", 'cut-video: the --from phrase "goodbye" is not in the transcript\n')
    assert not (tmp_path / "out").exists() and stubs.calls("ffmpeg") == []


def test_refuses_a_phrase_found_more_than_once(stubs, inputs, tmp_path, capsys):
    code, _o, e = refusal(capsys, "--from", "is", "--out", tmp_path / "out", *inputs)
    assert (code, e) == (6, ('cut-video: the --from phrase "is" is found 2 times, at 00:00:00.000 and '
                            '00:00:21.000: give a longer phrase, found only once\n'))


def test_refuses_an_end_before_the_start(stubs, inputs, tmp_path, capsys):
    code, _o, e = refusal(capsys, "--from", "today", "--to", "welcome", "--out", tmp_path / "out", *inputs)
    assert (code, e) == (7, ("cut-video: the --to phrase ends at 00:00:09.500, not after the --from phrase "
                            "begins at 00:00:09.500\n"))
    assert not (tmp_path / "out").exists()


def test_refuses_when_ffmpeg_is_missing(stubs, inputs, tmp_path, capsys):
    stubs.remove("ffmpeg")
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", *inputs)
    assert (code, e) == (8, ("cut-video: ffmpeg is not installed (or not on PATH). Install it with: "
                            "brew install ffmpeg\n"))
    assert not (tmp_path / "out").exists() and stubs.calls() == []


def test_refuses_when_ffprobe_is_missing(stubs, inputs, tmp_path, capsys):
    stubs.remove("ffprobe")
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", *inputs)
    assert (code, e) == (8, ("cut-video: ffprobe is not installed (or not on PATH). Install it with: "
                            "brew install ffmpeg\n"))


def test_refuses_a_video_ffprobe_cannot_read(stubs, inputs, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FFPROBE_EXIT", "1")
    video, srt = inputs
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", video, srt)
    assert (code, e) == (10, (f"cut-video: ffprobe could not read {video} as a video: {video}: Invalid data found when "
                             "processing input\n"))
    assert not (tmp_path / "out").exists() and stubs.calls("ffmpeg") == []


def test_refuses_when_ffprobe_gives_no_duration(stubs, inputs, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FFPROBE_OUTPUT", "N/A")
    video, srt = inputs
    code, _o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", video, srt)
    assert (code, e) == (10, f"cut-video: ffprobe gave no duration for {video} ('N/A'), so it cannot be cut.\n")


def test_a_failed_ffmpeg_run_leaves_no_partial_file(stubs, inputs, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FFMPEG_EXIT", "1")
    video, srt = inputs
    before = (digest(video), digest(srt))
    code, o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", video, srt)
    assert (code, o) == (11, "")
    assert e == "cut-video: ffmpeg failed (exit 1), so nothing was written: Conversion failed!\n"
    assert os.listdir(tmp_path / "out") == []
    assert (digest(video), digest(srt)) == before


def test_refuses_an_output_folder_already_holding_a_file_it_would_write(stubs, inputs, tmp_path, capsys):
    out = tmp_path / "out"
    out.mkdir()
    (out / "talk-cut.txt").write_text("mine", encoding="utf-8")
    code, _o, e = refusal(capsys, "--from", "today", "--out", out, *inputs)
    assert (code, e) == (9, "cut-video: {} already exists, and nothing is ever written over. Move it, or give "
                            "another --out.\n".format(out / "talk-cut.txt"))
    assert os.listdir(out) == ["talk-cut.txt"] and (out / "talk-cut.txt").read_text(encoding="utf-8") == "mine"
    assert stubs.calls("ffmpeg") == []


def test_refuses_an_output_folder_that_is_a_file(stubs, inputs, tmp_path, capsys):
    out = tmp_path / "out"
    out.write_text("mine", encoding="utf-8")
    code, _o, e = refusal(capsys, "--from", "today", "--out", out, *inputs)
    assert (code, e) == (9, (f"cut-video: cannot make the output folder {out}: file exists. Give another "
                            "--out.\n"))
    assert out.read_text(encoding="utf-8") == "mine"



def test_refuses_an_output_folder_it_cannot_make(stubs, inputs, tmp_path, capsys):
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        code, _o, e = refusal(capsys, "--from", "today", "--out", locked / "out", *inputs)
    finally:
        locked.chmod(0o700)
    assert (code, e) == (9, "cut-video: cannot make the output folder {}: permission denied. Give another "
                            "--out.\n".format(locked / "out"))


def test_stopping_it_with_ctrl_c_leaves_no_partial_file_and_no_traceback(stubs, inputs, tmp_path, capsys,
                                                                          monkeypatch):
    import subprocess
    real_run = subprocess.run

    def interrupted(args, **kwargs):
        if args[0] == "ffmpeg":
            real_run(args, **kwargs)
            raise KeyboardInterrupt
        return real_run(args, **kwargs)
    monkeypatch.setattr(subprocess, "run", interrupted)
    code, o, e = refusal(capsys, "--from", "today", "--out", tmp_path / "out", *inputs)
    assert (code, o, e) == (130, "", "cut-video: stopped, so nothing was written.\n")
    assert os.listdir(tmp_path / "out") == []


def test_dry_run_says_where_it_would_cut_and_how_and_writes_nothing(stubs, inputs, tmp_path, capsys):
    video, srt = inputs
    out = tmp_path / "out"
    code = run_cut_video("--dry-run", "--from", "welcome to", "--to", "thank you", "--out", out, video, srt)
    o, e = capsys.readouterr()
    assert (code, e) == (0, "")
    assert o == (
        'Start: 00:00:04.000, the start of cue 2 (--from "welcome to")\n'
        "      1  00:00:00.000 --> 00:00:04.000  Is this thing on?\n"
        "  >   2  00:00:04.000 --> 00:00:09.500  Welcome to the show.\n"
        "      3  00:00:09.500 --> 00:00:15.000  Today, cutting video.\n"
        'End: 00:00:21.000, the end of cue 4 (--to "thank you")\n'
        "      3  00:00:09.500 --> 00:00:15.000  Today, cutting video.\n"
        "  >   4  00:00:15.000 --> 00:00:21.000  That's all, thank you.\n"
        "      5  00:00:21.000 --> 00:00:25.000  Is it off yet?\n"
        "Length: 00:00:17.000 of the video's 00:00:26.000, 3 cues.\n"
        f"Would write {out}/talk-cut.mp4, talk-cut.srt and talk-cut.txt.\n"
        "ffmpeg command (the video is written under a temporary name, renamed when complete):\n"
        f"  ffmpeg -nostdin -hide_banner -loglevel error -y -ss 4.000 -i {video} -t 17.000 -map 0:v:0 -map '0:a:0?' "
        f"-c:v libx264 -c:a aac -movflags +faststart -f mp4 {out}/talk-cut.mp4\n"
        "Dry run: nothing written.\n")
    assert not out.exists() and stubs.calls("ffmpeg") == []


def test_dry_run_with_one_end_left_alone_says_so(stubs, inputs, tmp_path, capsys):
    code = run_cut_video("--dry-run", "--to", "off yet", "--out", tmp_path / "out", *inputs)
    o, e = capsys.readouterr()
    assert (code, e) == (0, "")
    assert o.startswith("Start: 00:00:00.000, the beginning of the video (no --from)\n"
                        'End: 00:00:25.000, the end of cue 5 (--to "off yet")\n')
    code = run_cut_video("--dry-run", "--from", "off yet", "--out", tmp_path / "out", *inputs)
    o, _e = capsys.readouterr()
    assert "\nEnd: 00:00:26.000, the end of the video (no --to)\nLength: 00:00:05.000" in o


def test_dry_run_says_when_the_video_ends_inside_the_last_cue(stubs, inputs, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("FFPROBE_OUTPUT", "23.000000")
    code = run_cut_video("--dry-run", "--to", "off yet", "--out", tmp_path / "out", *inputs)
    o, e = capsys.readouterr()
    assert (code, e) == (0, "")
    assert 'End: 00:00:23.000, the end of the video, inside cue 5 (--to "off yet")\n' in o

