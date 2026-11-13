"""The stub's tokenizer: phonemize() upper-cases and strips, as a fake the tests can see spliced
into a phoneme string, and logs each call like the model's create()."""

import json
import os


class Tokenizer:
    def __init__(self, espeak_config=None, vocab=None):
        pass

    def phonemize(self, text, lang="en-us", norm=True):
        with open(os.environ["KOKORO_STUB_LOG"], "a", encoding="utf-8") as f:
            f.write(json.dumps({"phonemize": {"text": text, "lang": lang}}, ensure_ascii=False) + "\n")
        return text.strip().upper()
