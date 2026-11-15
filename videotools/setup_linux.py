"""setup-linux: the Linux device shell's venv, packages, model check, config and environment lines, by
lobster-tools' prepare-venv (lobster-tools' Request 01; PLAN.md Settled 13 and 14). This keeps setup-linux's
flags, runs prepare-venv with this checkout as --project and the arguments as given, and gives back its exit code;
what prepare-venv does for this project is in prepare-venv.conf at the top of the checkout.

Standard library only; runs on whatever python3 the shell has (3.9 or later), and runs prepare-venv on the same.
"""

import argparse
import os
import subprocess
import sys

from videotools.cli import EXTERNAL, Failure, report

PROG = "setup-linux"
REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
SETTING = "LOBSTER_TOOLS"
HELP = '(README, "Running from the Linux device shell")'


def parser():
    p = argparse.ArgumentParser(
        prog=PROG,
        description="Prepare the Linux device shell for the video-tools commands, by lobster-tools' prepare-venv: "
                    "a venv outside the checkout with the packages, a check that the speech model (model.onnx and "
                    "voices.npz) is in place, a config naming it, and the three environment lines to export. "
                    f"prepare-venv is found in the lobster-tools checkout that {SETTING} names, else in "
                    "~/mnt/lobster-tools.")
    p.add_argument("--venv", required=True, metavar="DIR", help="the venv to make or reuse (never inside the checkout)")
    p.add_argument("--model", required=True, metavar="DIR", help="the folder holding model.onnx and voices.npz")
    p.add_argument("--conf", required=True, metavar="FILE", help="the config to write SPEECH_MODEL_DIR into")
    p.add_argument("--dry-run", action="store_true", help="check, say what would be done, make and write nothing")
    return p


def prepare_venv():
    """The path of lobster-tools' prepare-venv: in the checkout LOBSTER_TOOLS names when it is set, else in
    ~/mnt/lobster-tools; Failure (exit 4) naming where it looked when it is not there."""
    named = os.environ.get(SETTING)
    folder = named or os.path.join(os.path.expanduser("~"), "mnt", "lobster-tools")
    path = os.path.join(folder, "prepare-venv")
    if os.path.isfile(path):
        return path
    if named:
        raise Failure(f"lobster-tools' prepare-venv is not in {folder}, which {SETTING} names; set {SETTING} to the "
                      f"lobster-tools checkout {HELP}", EXTERNAL)
    raise Failure(f"lobster-tools' prepare-venv is not in {folder}, and {SETTING} is not set; connect lobster-tools "
                  f"there, or set {SETTING} to its checkout {HELP}", EXTERNAL)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        path = prepare_venv()
    except Failure as f:
        return report(PROG, f)
    command = [sys.executable, path, "--project", REPO, "--venv", args.venv, "--model", args.model,
               "--conf", args.conf] + (["--dry-run"] if args.dry_run else [])
    return subprocess.run(command, check=False).returncode
