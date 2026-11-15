"""The stand-in programs themselves: each test links a shared file from tests/stubs/ into its own folder
rather than writing a new one (macOS takes about a seventh of a second over the first run of a script
file it has not seen), and the run says at its end if a test wrote over a shared one."""

import os

from tests.tier2.conftest import STUBS, stand_in_digests, written_over


def test_a_shared_stand_in_written_over_or_removed_is_named(tmp_path):
    (tmp_path / "a.sh").write_text("#!/bin/sh\necho a\n")
    (tmp_path / "b.sh").write_text("#!/bin/sh\necho b\n")
    (tmp_path / "c.sh").write_text("#!/bin/sh\necho c\n")
    before = stand_in_digests(str(tmp_path))
    assert written_over(before, str(tmp_path)) == []
    (tmp_path / "a.sh").write_text("#!/bin/sh\necho written over\n")
    (tmp_path / "c.sh").unlink()
    assert written_over(before, str(tmp_path)) == ["a.sh", "c.sh"]


def test_cut_videos_ffmpeg_and_ffprobe_are_links_to_one_shared_file(stubs):
    for name in ("ffmpeg", "ffprobe"):
        path = stubs.bin / name
        assert os.path.islink(path) and os.readlink(path) == os.path.join(STUBS, "ffstub.sh")


def test_the_fake_media_ffmpeg_and_ffprobe_are_links_to_one_shared_file(ffstub):
    folder = ffstub["PATH"].split(os.pathsep)[0]
    for name in ("ffmpeg", "ffprobe"):
        path = os.path.join(folder, name)
        assert os.path.islink(path) and os.readlink(path) == os.path.join(STUBS, "fakemedia.sh")
