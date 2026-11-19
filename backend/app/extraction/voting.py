"""Pure functions that vote over independent reads: values, titles, and whole transcriptions."""

import difflib
import html
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Sequence
from typing import Any

Tokens = list[str]
Span = tuple[int, int]


def _json_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True)


def vote(
    values: Sequence[Any], key: Callable[[Any], str] = _json_key
) -> tuple[bool, str | None, int]:
    """Winner if it has at least two votes and strictly more than any other value.

    Returns (has a winner, the winner as a JSON string, its vote count). Values that `key` maps
    to the same string count as one value.
    """
    groups: dict[str, list[Any]] = defaultdict(list)
    for value in values:
        groups[key(value)].append(value)
    ranked = sorted(groups.values(), key=len, reverse=True)
    if not ranked or len(ranked[0]) < 2:
        return False, None, 0
    if len(ranked) > 1 and len(ranked[0]) == len(ranked[1]):
        return False, None, 0
    winner = Counter(json.dumps(v) for v in ranked[0]).most_common(1)[0][0]
    return True, winner, len(ranked[0])


def clean(out: dict[str, Any]) -> dict[str, Any]:
    """Undo reader quirks: HTML entities (&amp;) and the word null instead of a JSON null."""
    out = dict(out)
    for name in ("title", "text"):
        if isinstance(out.get(name), str):
            value = html.unescape(out[name]).strip()
            out[name] = None if value.lower() in ("", "null", "none") else value
    return out


# ---------------------------------------------------------------- spelling


def bare(word: str) -> str:
    """A word for comparing: no punctuation, no case."""
    return re.sub(r"[^\w]", "", word).casefold()


def spelling_flags(text: str, proofs: list[dict[str, str]]) -> list[dict[str, str]]:
    """Misspellings the proofreaders saw that the transcription has in a corrected form.

    Each proof is `{"printed": ..., "context": ...}`. A flag is a printed word that is not in the
    text but is close to a word that is.
    """
    words = {bare(t): t for t in tokens(text)}
    flags: dict[str, dict[str, str]] = {}
    for proof in proofs:
        printed = bare(proof["printed"])
        if not printed or printed in words or printed in flags:
            continue
        close = difflib.get_close_matches(printed, words, n=1, cutoff=0.75)
        if close:
            flags[printed] = {
                "printed": proof["printed"],
                "transcribed": words[close[0]],
                "context": proof["context"],
            }
    return list(flags.values())


# ---------------------------------------------------------------- tokens


def tokens(text: str | None) -> Tokens:
    """Words and line breaks; bold and underline markup is dropped."""
    return re.findall(r"\S+|\n", (text or "").replace("**", "").replace("__", ""))


def detokenize(toks: Tokens) -> str:
    out = ""
    for tok in toks:
        out = out.rstrip(" ") + "\n" if tok == "\n" else out + tok + " "
    lines = "\n".join(line.rstrip() for line in out.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", lines).strip() + "\n"


def words_only(toks: Sequence[str]) -> tuple[str, ...]:
    """Tokens without layout and [image]-style markers, which readers place inconsistently."""
    return tuple(
        t for t in toks if t not in ("\n", "[", "]") and not re.fullmatch(r"\[[^\]]*\]", t)
    )


def space_dots(text: str) -> str:
    """Readers glue score dots to each other and to the word before them in different ways,
    which would split the word vote; one dot is one word."""
    text = re.sub(r"(\S)(?=●\()", r"\1 ", text)
    return re.sub(r"(●\([a-z]+\))(?=[●\w])", r"\1 ", text)


# ---------------------------------------------------------------- merging transcriptions


def _similarity(a: Tokens, b: Tokens) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _closest_to_others(reads: list[Tokens]) -> int:
    """Index of the read that resembles all the others most: the base to correct."""
    return max(range(len(reads)), key=lambda j: sum(_similarity(reads[j], t) for t in reads))


def _differences(base: Tokens, reads: list[Tokens], base_index: int) -> dict[Span, Counter]:
    """For each span of the base that some read has differently: what those reads have there."""
    alternatives: dict[Span, Counter] = defaultdict(Counter)
    for j, read in enumerate(reads):
        if j == base_index:
            continue
        matcher = difflib.SequenceMatcher(None, base, read, autojunk=False)
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op != "equal":
                alternatives[(i1, i2)][tuple(read[j1:j2])] += 1
    return alternatives


def _context(seq: Sequence[str]) -> str:
    return " ".join(x for x in seq if x != "\n")


def _only_minority_has_passage(base_span: Tokens, alternatives: Counter) -> bool:
    """A read has at least 5 more words here than the base. Readers drop text far more often
    than they invent it, so such a passage is flagged rather than voted away."""
    base_words = len(words_only(base_span))
    return any(len(words_only(alt)) >= base_words + 5 for alt in alternatives)


def _differs_in_words(base_span: Tokens, alternatives: Counter) -> bool:
    """False when the spans differ only in layout or [image] markers."""
    spans = {words_only(base_span)} | {words_only(alt) for alt in alternatives}
    return len(spans) > 1


def _unresolved(base: Tokens, span: Span, alternatives: Counter) -> dict[str, Any]:
    i1, i2 = span
    before, after = base[max(0, i1 - 4) : i1], base[i2 : i2 + 4]
    return {
        "kept": _context(base[max(0, i1 - 4) : i2 + 4]),
        "alternatives": [_context(before + list(alt) + after) for alt in alternatives],
    }


def merge_reads(texts: list[str]) -> tuple[str, list[dict[str, Any]]]:
    """Word-level majority over independent transcriptions. Start from the read closest to the
    others; a differing span is replaced when more reads agree on the replacement than on the
    base. Returns (text, unresolved spans)."""
    reads = [tokens(t) for t in texts]
    base_index = _closest_to_others(reads)
    base = reads[base_index]
    merged, unresolved = list(base), []
    # Last span first, so that replacing a span does not move the ones still to do.
    for span, alternatives in sorted(_differences(base, reads, base_index).items(), reverse=True):
        i1, i2 = span
        best, best_votes = alternatives.most_common(1)[0]
        base_votes = len(reads) - sum(alternatives.values())
        if best_votes > base_votes:
            merged[i1:i2] = list(best)
            continue
        base_span = base[i1:i2]
        contested = (
            best_votes == base_votes
            or len(alternatives) > 1
            or _only_minority_has_passage(base_span, alternatives)
        )
        if contested and _differs_in_words(base_span, alternatives):
            unresolved.append(_unresolved(base, span, alternatives))
    return detokenize(merged), unresolved[::-1]


# ---------------------------------------------------------------- Tesseract comparison

_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})
_EDGE_PUNCTUATION = ".,:;!?()[]{}\"'*_#|>-–—•·"


def ocr_words(text: str) -> list[str]:
    """Words to compare a transcription with Tesseract's: case and spelling kept; markup, [image]
    markers, list bullets and punctuation around words dropped; quotes straightened."""
    text = re.sub(r"\[[^\]]*\]", " ", text.translate(_QUOTES))
    words = (w.strip(_EDGE_PUNCTUATION) for w in text.split())
    return [w for w in words if re.search(r"\w", w)]


def ocr_confirms(read: str, ocr: str | None) -> bool:
    """Tesseract read exactly the same words: two independent methods agree."""
    return bool(ocr and ocr_words(ocr)) and ocr_words(read) == ocr_words(ocr)
