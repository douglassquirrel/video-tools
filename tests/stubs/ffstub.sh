#!/bin/sh
# cut-video's stand-in for ffmpeg and ffprobe: tests/tier2/conftest.py links this one file into each test's
# folder under both names, so no test writes a new program (macOS takes about a seventh of a second over the
# first run of a script it has not seen). It runs ffstub.py, telling it the name it was called by.
# VIDEO_TOOLS_STUB_PYTHON and VIDEO_TOOLS_STUBS, set by conftest.py, name the Python and this folder.
FFSTUB_NAME=${0##*/} exec "$VIDEO_TOOLS_STUB_PYTHON" "$VIDEO_TOOLS_STUBS/ffstub.py" "$@"
