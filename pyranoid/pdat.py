"""Loader for PARRY's PDAT semantic-memory file.

PDAT is the response database recovered from the 1974 WAITS image. Each entry is
one of two record types, written in SAIL LISP read-syntax:

    (#B <name> <weight> <conceptualization>  <field>...)   ; belief / input unit
    (#E <name>                               <field>...)   ; response unit

Fields are inline ``KEYWORD value`` pairs. Known keywords:

    TOPIC   a list of topic atoms the unit belongs to
    RESP    the response unit (#E) this input unit selects
    ANAPH   an assoc list ((anaph-word . target) ...) for follow-up references
    NORMAL  (on #E) a list of candidate response sentences
    EXH     T -> once exhausted, switch to the "I already told you" responses
    SF/NN/FX  LISP semantic-function expressions (kept as raw s-expressions)
    PRED/CLASS/LIT  auxiliary tags (kept raw)

In the recovered text, unit ids are written with the SAIL glyphs ``λ`` (for #B
units, the original ^H prefix) and ``α`` (for #E units, the original ^B prefix).
This loader normalises them to ``H<nnnn>`` and ``B<nnnn>`` so ids are plain ASCII;
references inside conceptualisations and anaphora are normalised the same way.

Only the raw s-expression reading is done here plus light structuring; nothing is
interpreted. Interpretation (matching, emotion, selection) lives in later modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# S-expression reader
# ---------------------------------------------------------------------------

Atom = str  # atoms are plain strings; unit refs look like "H0050" / "B0080"


@dataclass(frozen=True)
class DottedPair:
    """A LISP dotted pair ``(car . cdr)`` — used in ANAPH and LIT fields."""

    car: object
    cdr: object


SExpr = "Atom | list | DottedPair"

# Structural characters. '.' is handled specially (dotted pair vs. decimal point).
_OPEN = {"(": ")", "[": "]"}
_CLOSE = {")", "["}


class _Reader:
    """Tokenises and reads SAIL LISP forms from `text`, starting at `pos`."""

    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def _skip_ws(self) -> None:
        while self.i < self.n and self.s[self.i] in " \t\r\n\f":
            self.i += 1

    def _read_atom(self) -> str:
        out: list[str] = []
        while self.i < self.n:
            c = self.s[self.i]
            if c in " \t\r\n\f()[]":
                break
            if c == "/" and self.i + 1 < self.n:
                # SAIL escape: next char is literal (e.g. "GANGSTERS/." -> "GANGSTERS.")
                out.append(self.s[self.i + 1])
                self.i += 2
                continue
            if c == ".":
                # A '.' inside a number (digit . digit) stays in the atom; a '.'
                # between/around other things is a dotted-pair separator.
                prev = out[-1] if out else ""
                nxt = self.s[self.i + 1] if self.i + 1 < self.n else ""
                if prev.isdigit() and nxt.isdigit():
                    out.append(c)
                    self.i += 1
                    continue
                break
            out.append(c)
            self.i += 1
        return _normalise("".join(out))

    def read(self):
        """Read one form; return the form, or _EOF at end of input."""
        self._skip_ws()
        if self.i >= self.n:
            return _EOF
        c = self.s[self.i]
        if c in _OPEN:
            return self._read_list(_OPEN[c])
        if c in (")", "]"):
            raise ValueError(f"unexpected {c!r} at {self.i}")
        if c == ".":
            # standalone dot outside a list — treat as atom (shouldn't happen)
            self.i += 1
            return "."
        return self._read_atom()

    def _read_list(self, closer: str):
        self.i += 1  # consume opener
        items: list = []
        while True:
            self._skip_ws()
            if self.i >= self.n:
                raise ValueError("unterminated list")
            c = self.s[self.i]
            if c in (")", "]"):
                self.i += 1
                return items
            if c == ".":
                nxt = self.s[self.i + 1] if self.i + 1 < self.n else ""
                if not nxt.isdigit():
                    # dotted pair: read cdr, expect close
                    self.i += 1
                    cdr = self.read()
                    self._skip_ws()
                    if self.i < self.n and self.s[self.i] in (")", "]"):
                        self.i += 1
                    car = items[0] if len(items) == 1 else items
                    return DottedPair(car, cdr)
            items.append(self.read())


_EOF = object()

_REF_RE = re.compile(r"[λα]\d+")


def _normalise(atom: str) -> str:
    """Map SAIL unit-ref glyphs to ASCII: λ0050 -> H0050, α0080 -> B0080.

    Applies anywhere the glyph appears (including @λ0010 -> @H0010).
    """
    if "λ" not in atom and "α" not in atom:
        return atom
    return atom.replace("λ", "H").replace("α", "B")


def _read_forms(text: str):
    r = _Reader(text)
    while True:
        form = r.read()
        if form is _EOF:
            return
        yield form


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Response:
    """One candidate thing PARRY can say, from a #E unit's NORMAL list.

    `words` is the plain-text sentence. `tags` holds any leading parenthesised
    markers such as (EXITS), (OFFENDED), or special forms like (2 RESP NORMAL),
    which direct behaviour rather than being spoken.
    """

    words: str
    tags: list = field(default_factory=list)
    raw: object = None

    def __str__(self) -> str:
        return self.words


@dataclass
class BeliefUnit:
    """A #B record: an input concept PARRY recognises."""

    name: str
    weight: int
    concept: list
    topic: list = field(default_factory=list)
    resp: str | None = None
    anaph: dict = field(default_factory=dict)
    fields: dict = field(default_factory=dict)  # PRED, CLASS, SF, FX, NN, LIT, ...
    raw: object = None


@dataclass
class ResponseUnit:
    """A #E record: a set of responses for a belief unit."""

    name: str
    normal: list = field(default_factory=list)  # list[Response]
    anaph: dict = field(default_factory=dict)
    exhaust: bool = False
    fields: dict = field(default_factory=dict)
    raw: object = None


@dataclass
class Memory:
    """The loaded PDAT: belief units (#B) and response units (#E).

    `duplicate_names` and the result of :meth:`dangling_responses` surface
    authentic quirks of Colby's 1974 data (a response unit defined twice, and
    belief units whose RESP points at a never-defined response). These are
    preserved rather than hidden; see all.doc's own bug notes.
    """

    beliefs: dict  # name -> BeliefUnit
    responses: dict  # name -> ResponseUnit
    order: list  # names in file order
    duplicate_names: list = field(default_factory=list)  # ids defined more than once

    def response_for(self, belief_name: str) -> ResponseUnit | None:
        b = self.beliefs.get(belief_name)
        if b is None or b.resp is None:
            return None
        return self.responses.get(b.resp)

    def dangling_responses(self) -> dict:
        """{belief_name: missing_resp_id} for RESP refs with no #E unit."""
        return {
            b.name: b.resp
            for b in self.beliefs.values()
            if b.resp is not None and b.resp not in self.responses
        }

    def __len__(self) -> int:
        return len(self.beliefs) + len(self.responses)


# ---------------------------------------------------------------------------
# Structuring
# ---------------------------------------------------------------------------

_FIELD_KEYWORDS = {
    "TOPIC", "RESP", "ANAPH", "NORMAL", "EXH",
    "SF", "NN", "FX", "PRED", "CLASS", "LIT",
}


def _parse_fields(items: list, start: int) -> dict:
    """Read inline ``KEYWORD value`` pairs from items[start:]."""
    out: dict = {}
    i = start
    while i < len(items):
        key = items[i]
        if isinstance(key, str) and key in _FIELD_KEYWORDS and i + 1 < len(items):
            out[key] = items[i + 1]
            i += 2
        else:
            # Unexpected stray token; skip it rather than misalign.
            i += 1
    return out


def _anaph_to_dict(value) -> dict:
    """Turn an ANAPH assoc list into {anaph_word: target}."""
    out: dict = {}
    if not isinstance(value, list):
        return out
    for pair in value:
        if isinstance(pair, DottedPair):
            out[str(pair.car)] = pair.cdr
        elif isinstance(pair, list) and len(pair) == 2:
            out[str(pair[0])] = pair[1]
    return out


def _to_response(entry) -> Response:
    """Turn one NORMAL entry (a list) into a Response."""
    tags: list = []
    words: list[str] = []
    if isinstance(entry, list):
        for tok in entry:
            if isinstance(tok, list):
                tags.append(tok)  # e.g. (EXITS), (OFFENDED)
            elif isinstance(tok, DottedPair):
                tags.append(tok)
            else:
                words.append(str(tok))
    else:
        words.append(str(entry))
    return Response(words=" ".join(words), tags=tags, raw=entry)


def _build_belief(items: list) -> BeliefUnit:
    name = items[1]
    try:
        weight = int(items[2])
    except (ValueError, IndexError):
        weight = 0
    concept = items[3] if len(items) > 3 and isinstance(items[3], list) else []
    fields = _parse_fields(items, 4)
    topic = fields.pop("TOPIC", []) or []
    resp = fields.pop("RESP", None)
    anaph = _anaph_to_dict(fields.pop("ANAPH", None))
    return BeliefUnit(
        name=name, weight=weight, concept=concept,
        topic=topic if isinstance(topic, list) else [topic],
        resp=resp, anaph=anaph, fields=fields, raw=items,
    )


def _build_response(items: list) -> ResponseUnit:
    name = items[1]
    fields = _parse_fields(items, 2)
    normal_raw = fields.pop("NORMAL", None)
    normal = [_to_response(e) for e in normal_raw] if isinstance(normal_raw, list) else []
    anaph = _anaph_to_dict(fields.pop("ANAPH", None))
    exhaust = str(fields.pop("EXH", "")).upper() == "T"
    return ResponseUnit(
        name=name, normal=normal, anaph=anaph, exhaust=exhaust,
        fields=fields, raw=items,
    )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------


def _strip_directory(text: str) -> str:
    """Drop the SAIL editor page directory that precedes the content.

    The directory ends at the ``ENDMK`` marker; content proper begins at the
    first form-feed after it. If neither is found, the whole text is returned.
    """
    mk = text.find("ENDMK")
    if mk == -1:
        return text
    ff = text.find("\f", mk)
    return text[ff + 1:] if ff != -1 else text[mk + len("ENDMK"):]


def load_pdat(path: str | Path) -> Memory:
    """Load a decoded PDAT text file into a :class:`Memory`.

    `path` should be the SAIL-decoded UTF-8 text (see recovered/text/pdatz.txt),
    produced with ``cat36 -Wdata8 -Xsail``.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    content = _strip_directory(text)

    beliefs: dict = {}
    responses: dict = {}
    order: list = []
    duplicate_names: list = []

    for form in _read_forms(content):
        if not isinstance(form, list) or not form:
            continue
        head = form[0]
        if head == "#B" and len(form) >= 2:
            unit = _build_belief(form)
            if unit.name in beliefs:
                duplicate_names.append(unit.name)
            beliefs[unit.name] = unit
            order.append(unit.name)
        elif head == "#E" and len(form) >= 2:
            unit = _build_response(form)
            if unit.name in responses:
                duplicate_names.append(unit.name)
            responses[unit.name] = unit
            order.append(unit.name)
        # else: comment forms (*** ... ***) and stray tokens are ignored

    return Memory(
        beliefs=beliefs, responses=responses, order=order,
        duplicate_names=duplicate_names,
    )
