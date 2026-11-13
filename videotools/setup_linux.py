"""setup-linux: make the device shell's venv, install the packages, check the model, write the
config, print the environment lines (training-video-tools' PLAN.md item 27, taken in at fc6091a).

Standard library only; runs on whatever python3 the shell has (3.9 or later).
"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys

from videotools import config
from videotools.cli import OK, REFUSED, USAGE, Failure, report

PROG = "setup-linux"
REPO = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
PACKAGES = ["numpy", "soundfile", "kokoro-onnx==0.6.1", "Pillow"]
IMPORTS = "import numpy, soundfile, kokoro_onnx, PIL"


def progress(message):
    sys.stderr.write(f"{PROG}: {message}\n")


def run(argv):
    """Run a program with an argument list (never a shell line); (exit code, its output)."""
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return p.returncode, p.stdout


def run_or_fail(argv, advice):
    """Run a set-up step; when it exits non-zero, Failure in words with its last lines and `advice`."""
    code, output = run(argv)
    if code != 0:
        last = output.strip().splitlines()[-5:]
        raise Failure(f"{' '.join(argv)} failed (exit {code}); its last lines:\n"
                      + "".join(f"  {line}\n" for line in last) + advice)


def ensure_venv(venv, dry):
    """Make the venv with the python3 on PATH when DIR/bin/python is missing; (its python, made now)."""
    python = os.path.join(venv, "bin", "python")
    if os.path.isfile(python):
        return python, False
    python3 = shutil.which("python3")
    if python3 is None:
        raise Failure("no python3 on PATH to make the venv with; install Python 3 or put it on PATH")
    if dry:
        print(f"Would make the venv at {venv}")
        return python, True
    run_or_fail(["python3", "-m", "venv", "--system-site-packages", venv],
                "Fix that (the venv module and pip must work on this machine) and run again")
    progress(f"made the venv at {venv}")
    return python, True


def ensure_packages(python, venv, dry, fresh):
    """Install the packages into the venv when its python cannot import them (a venv a dry run
    has not made cannot be asked, and would need them)."""
    if not (dry and fresh):
        code, _ = run([python, "-c", IMPORTS])
        if code == 0:
            return
    if dry:
        print(f"Would install {' '.join(PACKAGES)} into {venv}")
        return
    run_or_fail([python, "-m", "pip", "install"] + PACKAGES,
                "Fix that (the network, or a package's build needs) and run again; the venv is kept")
    progress(f"installed {' '.join(PACKAGES)} into {venv}")


def conf_lines(conf):
    """The config's lines as they are, [] when there is no file."""
    if not os.path.isfile(conf):
        return []
    with open(conf, encoding="utf-8") as f:
        return f.read().splitlines(True)


def is_model_line(line):
    body = line.split("#", 1)[0].strip()
    return "=" in body and body.split("=", 1)[0].strip() == "SPEECH_MODEL_DIR"


def ensure_conf(conf, model, dry):
    """Write SPEECH_MODEL_DIR=model into the config when the file is missing or says otherwise,
    keeping every other line; a file that already says it is left untouched."""
    try:
        settings = config.read(conf)
    except config.ConfigError as e:
        raise Failure(f"{conf} cannot be used as it is; fix it or name another file with --conf:\n{e}") from e
    if settings.get("SPEECH_MODEL_DIR") == model:
        return
    if dry:
        print(f"Would write {conf} with SPEECH_MODEL_DIR={model}")
        return
    lines = conf_lines(conf)
    new = f"SPEECH_MODEL_DIR={model}\n"
    if any(is_model_line(line) for line in lines):
        lines = [new if is_model_line(line) else line for line in lines]
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(new)
    os.makedirs(os.path.dirname(conf), exist_ok=True)
    with open(conf, "w", encoding="utf-8") as f:
        f.writelines(lines)
    progress(f"wrote {conf}")


README_POINTER = 'as the README\'s "One-time set-up of the speech model" says'


def model_problems(model):
    """What the model folder lacks, a message each: the folder, model.onnx, voices.npz."""
    if not os.path.isdir(model):
        return [f"the model folder {model} does not exist; download the model into it {README_POINTER}"]
    problems = []
    if not os.path.isfile(os.path.join(model, "model.onnx")):
        problems.append(f"the model folder {model} has no model.onnx; download it {README_POINTER}")
    if not os.path.isfile(os.path.join(model, "voices.npz")):
        problems.append(f"the model folder {model} has no voices.npz; make it from the voices {README_POINTER}")
    return problems


def environment_lines(venv, conf):
    return [f"export VIDEO_TOOLS_PYTHON={shlex.quote(os.path.join(venv, 'bin', 'python'))}",
            f"export VIDEO_TOOLS_CONF={shlex.quote(conf)}",
            "export PYTHONDONTWRITEBYTECODE=1"]


def refuse_inside_checkout(venv):
    """The Linux venv must not be in this repository: it would shadow the Mac's .venv (README)."""
    real = os.path.realpath(venv)
    if real == REPO or real.startswith(REPO + os.sep):
        raise Failure(f"--venv {venv} is inside this checkout ({REPO}); the Linux venv must be made outside it, "
                      "or it would shadow the Mac's .venv (README, \"Running from the Linux device shell\")", USAGE)


def parse(argv):
    p = argparse.ArgumentParser(
        prog=PROG,
        description="Prepare the Linux device shell for the video-tools commands: a venv outside the "
                    "checkout with the packages, a check that the speech model (model.onnx and voices.npz) "
                    "is in place, a config naming it, and the three environment lines to export.")
    p.add_argument("--venv", required=True, metavar="DIR", help="the venv to make or reuse (never inside the checkout)")
    p.add_argument("--model", required=True, metavar="DIR", help="the folder holding model.onnx and voices.npz")
    p.add_argument("--conf", required=True, metavar="FILE", help="the config to write SPEECH_MODEL_DIR into")
    p.add_argument("--dry-run", action="store_true", help="check, say what would be done, make and write nothing")
    return p.parse_args(argv)


def main(argv=None):
    args = parse(argv)
    venv, model, conf = (os.path.abspath(p) for p in (args.venv, args.model, args.conf))
    try:
        refuse_inside_checkout(args.venv)
        python, fresh = ensure_venv(venv, args.dry_run)
        ensure_packages(python, venv, args.dry_run, fresh)
        ensure_conf(conf, model, args.dry_run)
    except Failure as f:
        return report(PROG, f)
    problems = model_problems(model)
    if problems:
        for problem in problems:
            progress(problem)
        return REFUSED
    for line in environment_lines(venv, conf):
        print(line)
    return OK
