"""prepare-venv.conf, the file lobster-tools' prepare-venv reads for setup-linux (PLAN.md Settled 13): its keys, and
that it names the packages requirements.txt installs and every command imports through cli.need."""

import os
import re

from videotools import cli, config

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
KNOWN = {"ENV_PREFIX", "REQUIREMENTS", "IMPORTS", "MODEL_FILES", "MODEL_SETTING", "MODEL_HELP"}   # prepare-venv's keys


def read(name):
    """KEY=value lines, without comments or blank lines, as prepare-venv reads them."""
    with open(os.path.join(REPO, name), encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return dict(line.split("=", 1) for line in lines)


def requirement_names():
    with open(os.path.join(REPO, "requirements.txt"), encoding="utf-8") as f:
        lines = [line.split("#")[0].strip() for line in f]
    return {re.split(r"[=<>!~ ]", line)[0] for line in lines if line}


def test_prepare_venv_conf_gives_this_projects_details_with_only_keys_prepare_venv_knows():
    conf = read("prepare-venv.conf")
    assert set(conf) <= KNOWN
    assert {k: conf[k] for k in ("ENV_PREFIX", "REQUIREMENTS", "MODEL_FILES", "MODEL_SETTING")} == {
        "ENV_PREFIX": "VIDEO_TOOLS", "REQUIREMENTS": "requirements.txt", "MODEL_FILES": "model.onnx voices.npz",
        "MODEL_SETTING": "SPEECH_MODEL_DIR"}
    assert conf["MODEL_SETTING"] in config.KEYS
    assert conf["MODEL_HELP"] == "the README's \"One-time set-up of the speech model\""


def test_its_imports_are_the_packages_the_commands_need_and_requirements_txt_installs():
    imports = set(read("prepare-venv.conf")["IMPORTS"].split())
    assert imports == set(cli.PACKAGES)
    assert requirement_names() == {pip for pip, _spec in cli.PACKAGES.values()}
