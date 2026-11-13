"""Non-negotiable 1: the package never imports a networking module."""

import os
import re
import subprocess
import sys

PACKAGE = os.path.join(os.path.dirname(__file__), "..", "..", "videotools")
FORBIDDEN = ("socket", "urllib", "http", "ssl", "requests", "ftplib", "smtplib", "httpx")


def test_no_module_in_the_package_imports_a_networking_module():
    offenders = []
    for name in sorted(os.listdir(PACKAGE)):
        if name.endswith(".py"):
            with open(os.path.join(PACKAGE, name), encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if re.match(r"^\s*(import|from)\s+({})\b".format("|".join(FORBIDDEN)), line):
                        offenders.append(f"{name}:{n}: {line.strip()}")
    assert offenders == []


def test_importing_every_module_loads_no_networking_module():
    modules = sorted(n[:-3] for n in os.listdir(PACKAGE) if n.endswith(".py") and n != "__init__.py")
    code = ("import sys, importlib\n"
            f"for m in {modules!r}: importlib.import_module('videotools.' + m)\n"
            f"print(sorted(m for m in sys.modules if m.split('.')[0] in {FORBIDDEN!r}))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=os.path.join(PACKAGE, ".."), check=True).stdout
    assert out.strip() == "[]"
