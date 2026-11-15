#!/bin/sh
# The fake-media stand-in for ffmpeg and ffprobe (stills, compare-video, narrate): tests/tier2/conftest.py
# links this one file into each test's folder under both names, so no test writes a new program. It runs
# fakemedia.py, telling it the name it was called by, without coverage's hook (it is not code under test,
# and starts in a tenth of the time without it). VIDEO_TOOLS_STUB_PYTHON and VIDEO_TOOLS_STUBS, set by
# conftest.py, name the Python and this folder.
unset COVERAGE_PROCESS_START
FFSTUB_NAME=${0##*/} exec "$VIDEO_TOOLS_STUB_PYTHON" "$VIDEO_TOOLS_STUBS/fakemedia.py" "$@"
