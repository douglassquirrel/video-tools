"""The fixed vocabulary in videotools.phonemes equals the installed kokoro-onnx package's, so an
upgrade that changes it fails here rather than letting narrate's span check drift (the package is a
library in the venv; no model file is needed)."""

import json
import os

from videotools import phonemes


def test_the_fixed_vocabulary_equals_the_installed_packages():
    import kokoro_onnx
    with open(os.path.join(os.path.dirname(kokoro_onnx.__file__), "config.json"), encoding="utf-8") as f:
        vocab = json.load(f)["vocab"]
    assert set(phonemes.VOCAB) == set(vocab)
