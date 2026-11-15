#!/bin/sh
# setup-linux's stand-in for python3 and for the venv's python: tests/tier2/test_setup_linux.py links this
# one file in as python3, and pystub.py links it in as each venv's bin/python, so no test writes a new
# program. It runs pystub.py, telling it the path it was called by, without coverage's hook.
# VIDEO_TOOLS_STUB_PYTHON and VIDEO_TOOLS_STUBS, set by conftest.py, name the Python and this folder.
unset COVERAGE_PROCESS_START
PYSTUB_SELF=$0 exec "$VIDEO_TOOLS_STUB_PYTHON" "$VIDEO_TOOLS_STUBS/pystub.py" "$@"
