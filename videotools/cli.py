"""What narrate, stills, compare-video and setup-linux share: exit codes, errors in words on
stderr, refusing to overwrite (taken in from training-video-tools at fc6091a; cut-video has its own).

Standard library only; runs on Python 3.9.
"""

import os
import sys

OK = 0            # success, or --dry-run with everything checked
USAGE = 2         # bad arguments
REFUSED = 3       # an input refuses: malformed, missing, output exists; nothing written
EXTERNAL = 4      # an external program or package is missing or failed


class Failure(Exception):
    """A failure the command reports in words and exits with `code`."""

    def __init__(self, message, code=REFUSED):
        super().__init__(message)
        self.code = code


def report(prog, failure):
    """Print a Failure on stderr as `prog: message` and return its exit code."""
    sys.stderr.write(f"{prog}: {failure}\n")
    return failure.code


# The pip name and install line of each module a command may need; everything else is standard library.
PACKAGES = {"numpy": ("numpy", "numpy"), "soundfile": ("soundfile", "soundfile"), "PIL": ("Pillow", "Pillow"),
            "kokoro_onnx": ("kokoro-onnx", '"kokoro-onnx==0.6.1"')}
DEVICE_SHELL_HINT = ('; from the Linux device shell, set VIDEO_TOOLS_PYTHON to a Python that has it '
                     '(README, "Running from the Linux device shell")')


def need(module):
    """Import a package a command needs and return it; if this Python lacks it, Failure (exit 4)
    naming the package and its install line, and the device shell when VIDEO_TOOLS_PYTHON is unset."""
    import importlib
    try:
        return importlib.import_module(module)
    except ImportError as e:
        name, spec = PACKAGES.get(module, (module, module))
        hint = "" if os.environ.get("VIDEO_TOOLS_PYTHON") else DEVICE_SHELL_HINT
        raise Failure(f"the Python package '{name}' is not installed in this Python ({sys.executable}); "
                      f"install it with .venv/bin/pip install {spec}{hint}", EXTERNAL) from e


def refuse_existing(path):
    """Raise Failure if `path` exists: no command writes over a file."""
    if os.path.lexists(path):
        raise Failure(f"{path} already exists; give a new name")
