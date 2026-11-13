"""[[…]] spans of phonemes in a say: line (training-video-tools' PLAN.md item 13). Standard library; Python 3.9.

A span's contents go to the speech model as phonemes as they stand; the text around it is
phonemized by the model's own tokenizer and the two are spliced with the spaces as written.
The model's tokenizer drops any symbol outside its vocabulary silently, so `problems` names
them first.
"""

# The 114 symbols of kokoro-onnx 0.6.1's tokenizer vocabulary (its `config.json`, "vocab", in
# id order, the space among them), copied 10 October 2026; tests/tier2/test_phonemes_vocab.py
# asserts this equals the installed package's.
VOCAB = (";:,.!?\u2014\u2026\u0022()\u201c\u201d \u0303\u02a3\u02a5\u02a6\u02a8\u1d5d\uab67AIOQSTWY\u1d4aa"
         "bcdefhijklmnopqrstuvwxyz\u0251\u0250\u0252\u00e6\u03b2\u0254\u0255\u00e7\u0256\u00f0\u02a4\u0259"
         "\u025a\u025b\u025c\u025f\u0261\u0265\u0268\u026a\u029d\u026f\u0270\u014b\u0273\u0272\u0274\u00f8"
         "\u0278\u03b8\u0153\u0279\u027e\u027b\u0281\u027d\u0282\u0283\u0288\u02a7\u028a\u028b\u028c\u0263"
         "\u0264\u03c7\u028e\u0292\u0294\u02c8\u02cc\u02d0\u02b0\u02b2\u2193\u2192\u2197\u2198\u1d7b")

OPEN, CLOSE = "[[", "]]"


def parts(text):
    """[(piece, is_span)]: the text parts and the spans of a say: line, in order, spaces kept.
    An unclosed '[[' is kept as text (problems() reports it)."""
    out, i = [], 0
    while i < len(text):
        a = text.find(OPEN, i)
        b = text.find(CLOSE, a + 2) if a >= 0 else -1
        if a < 0 or b < 0:
            out.append((text[i:], False))
            break
        if a > i:
            out.append((text[i:a], False))
        out.append((text[a + 2:b], True))
        i = b + 2
    return out


def has_span(text):
    return any(is_span for _, is_span in parts(text))


def problems(text):
    """What is wrong with the spans of a say: line, in plain words."""
    out, i = [], 0
    while True:
        a = text.find(OPEN, i)
        c = text.find(CLOSE, i)
        if c >= 0 and (a < 0 or c < a):
            out.append(f"'{CLOSE}' at character {c + 1} has no '{OPEN}' before it")
            i = c + 2
            continue
        if a < 0:
            break
        b = text.find(CLOSE, a + 2)
        if b < 0:
            out.append(f"'{OPEN}' at character {a + 1} is never closed with '{CLOSE}'")
            break
        span = text[a + 2:b]
        if not span:
            out.append(f"'{OPEN}{CLOSE}' at character {a + 1} is empty")
        seen = set()
        for ch in span:
            if ch not in VOCAB and ch not in seen:
                seen.add(ch)
                out.append(f"'{ch}' (U+{ord(ch):04X}) in '{OPEN}{span}{CLOSE}' is not a symbol the voice knows")
        i = b + 2
    return out


def splice(text, phonemize):
    """The phoneme string for a say: line: each text part through `phonemize` (which strips
    whitespace, so the part's own leading and trailing spaces are put back), each span as it
    stands, joined in order."""
    out = []
    for piece, is_span in parts(text):
        if is_span:
            out.append(piece)
        else:
            core = piece.strip()
            lead = piece[:len(piece) - len(piece.lstrip())]
            trail = piece[len(piece.rstrip()):]
            out.append(lead + (phonemize(core) if core else "") + trail)
    return "".join(out).strip()


QUIET = "sfθʃh"   # training-video-tools' item 30, 1: the voiceless fricatives, said too faintly at the start of a cue


def lead_in(given):
    """The phoneme string as the voice is given it (training-video-tools' item 30, 1): `, ` in front, and a quiet first
    consonant doubled, so the voice says it in full at speed 1.5 (Squirrel's choice, by ear)."""
    given = given.lstrip()
    if not given:
        return given
    return ", " + (given[0] if given[0] in QUIET else "") + given
