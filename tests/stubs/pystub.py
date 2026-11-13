"""A stand-in for the python3 on PATH and for the venv's python it makes (tests/tier2/test_setup_linux.py
puts `python3` on PATH as a script that runs this with PYSTUB_SELF naming itself).

Every call is appended as a JSON line {"python": PYSTUB_SELF, "args": [...]} to PYSTUB_LOG.
`-m venv [--system-site-packages] DIR` makes DIR/bin/python, another such script; `-c "import …"`
succeeds when the venv holding this python has an `installed` file, else fails as a missing module
does; `-m pip install …` writes that file with the names given. PYSTUB_FAIL=venv or pip makes
that step exit 1 with a line like the real program's; pip-noisy makes pip fail with eight lines. Nothing here is real Python or pip.
"""

import json
import os
import sys

REAL = sys.executable
HERE = os.path.realpath(__file__)


def record(args):
    log = os.environ.get("PYSTUB_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"python": os.environ.get("PYSTUB_SELF", ""), "args": args}) + "\n")


def script_for(path):
    return f"#!/bin/sh\nunset COVERAGE_PROCESS_START\nPYSTUB_SELF='{path}' exec '{REAL}' '{HERE}' \"$@\"\n"


def main(args):
    record(args)
    fail = os.environ.get("PYSTUB_FAIL")
    me = os.environ.get("PYSTUB_SELF", "")
    venv = os.path.dirname(os.path.dirname(me))
    if args[:2] == ["-m", "venv"]:
        if fail == "venv":
            sys.stderr.write(f"Error: Command '['{args[-1]}/bin/python', '-m', 'ensurepip']' returned non-zero exit status 1.\n")
            return 1
        target = os.path.join(args[-1], "bin", "python")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(script_for(target))
        os.chmod(target, 0o755)
        return 0
    if args[:1] == ["-c"]:
        if os.path.isfile(os.path.join(venv, "installed")):
            return 0
        sys.stderr.write("Traceback (most recent call last):\n  File \"<string>\", line 1, in <module>\n"
                         "ModuleNotFoundError: No module named 'numpy'\n")
        return 1
    if args[:3] == ["-m", "pip", "install"]:
        if fail == "pip-noisy":                # more than five lines, as a real build failure gives
            sys.stderr.write("".join(f"build step {i}\n" for i in range(1, 9)))
            return 1
        if fail == "pip":
            sys.stderr.write("ERROR: Could not find a version that satisfies the requirement numpy (from versions: none)\n"
                             "ERROR: No matching distribution found for numpy\n")
            return 1
        with open(os.path.join(venv, "installed"), "w", encoding="utf-8") as f:
            f.write("\n".join(args[3:]) + "\n")
        sys.stdout.write("Successfully installed " + " ".join(args[3:]) + "\n")
        return 0
    sys.stderr.write(f"pystub: unexpected arguments: {args}\n")
    return 9


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
