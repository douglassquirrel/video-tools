"""A stand-in for lobster-tools' prepare-venv, for setup-linux's tests. tests/tier2/test_setup_linux.py links this one
file into a test's folder as `prepare-venv` (setup-linux runs it with its own Python, as it runs the real one). It
records the Python that ran it, its arguments and its working folder as one JSON line in PREPARE_VENV_STUB_LOG,
prints an export line on stdout and a progress line on stderr, and exits with PREPARE_VENV_STUB_EXIT (default 0)."""

import json
import os
import sys

with open(os.environ["PREPARE_VENV_STUB_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps({"python": sys.executable, "args": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
print("export VIDEO_TOOLS_PYTHON=/stand-in/venv/bin/python")
sys.stderr.write("prepare-venv: the stand-in ran\n")
sys.exit(int(os.environ.get("PREPARE_VENV_STUB_EXIT", "0")))
