"""Read ~/.video-tools.conf: KEY=value, # comments, optional quotes, ~ for home. Read, never run.

Standard library only; runs on Python 3.9.
"""

import os

KEYS = ("SPEECH_MODEL_DIR", "VOICE")


class ConfigError(Exception):
    """A config file that cannot be used, every problem on its own line."""


def path():
    """The config file: $VIDEO_TOOLS_CONF if set, else ~/.video-tools.conf."""
    return (os.environ.get("VIDEO_TOOLS_CONF")
            or os.path.join(os.path.expanduser("~"), ".video-tools.conf"))


def read(conf_path=None):
    """The settings in the file as {KEY: value}; {} when there is no file."""
    conf_path = conf_path or path()
    if not os.path.isfile(conf_path):
        return {}
    settings, problems = {}, []
    with open(conf_path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if "=" not in line:
                problems.append(f"{conf_path}: line {n}: not KEY=value: {line}")
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key not in KEYS:
                problems.append(f"{conf_path}: line {n}: unknown setting '{key}' (the settings are {', '.join(KEYS)})")
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key.endswith("_DIR"):
                value = os.path.expanduser(value)
            settings[key] = value
    if problems:
        raise ConfigError("\n".join(problems))
    return settings
