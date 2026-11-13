"""A stand-in for the kokoro_onnx package: records every call, returns a known waveform.

The waveform for a text of W words (tokens with a letter or digit in them) is 0.1 s of silence, a tone of 0.5 + 0.25 W seconds, and
0.3 s of silence, at 24,000 Hz, peak 0.5. Calls are appended as JSON lines to the file named
by KOKORO_STUB_LOG. Set KOKORO_STUB_FAIL to make create() raise, as the real model would on a
bad input.
"""

import json
import os

import numpy as np

RATE = 24000


class Kokoro:
    def __init__(self, model_path, voices_path):
        from kokoro_onnx.tokenizer import Tokenizer
        self.model_path, self.voices_path = model_path, voices_path
        self.tokenizer = Tokenizer()
        self._log({"init": [model_path, voices_path]})

    def _log(self, entry):
        with open(os.environ["KOKORO_STUB_LOG"], "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_voices(self):
        return ["af_heart", "bm_george", "zz_test"]

    def create(self, text, voice, speed, lang, is_phonemes=False):
        self._log({"create": {"text": text, "voice": voice, "speed": speed, "lang": lang, "is_phonemes": is_phonemes}})
        if os.environ.get("KOKORO_STUB_FAIL"):
            raise RuntimeError("stub: the model failed on purpose")
        words = len([w for w in text.split() if any(ch.isalnum() for ch in w)])   # a lone ',' is not a word
        tone = np.sin(np.arange(int(RATE * (0.5 + 0.25 * words))) * 0.05).astype(np.float32) * 0.5
        samples = np.concatenate([np.zeros(int(RATE * 0.1), np.float32), tone, np.zeros(int(RATE * 0.3), np.float32)])
        return samples, RATE
