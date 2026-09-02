"""Loaders for PARRY's lexical and pattern data files (original/src/).

Formats verified against the 1974 sources. The important cross-cutting detail:
unit identifiers are written with a literal 0x08 byte (`^H`) prefixing four
digits, plus `P####`, `SP##`, and `NIL`. Files are read as bytes and 0x08 is
mapped to 'H' so unit ids read as plain ASCII ("H1410"), matching the pdat
loader's naming. Two other control prefixes appear only in the affix tables:
0x18 (`^X`, a part-of-speech recast) and 0x10 (`^P`, a constituent pointer).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Bundled copies of PARRY's data files ship inside the package, so the port runs
# standalone without the original source tree. Source: original/src/.
DATA_DIR = Path(__file__).resolve().parent / "data"

BS = 0x08   # ^H  unit prefix
CAN = 0x18  # ^X  POS-recast marker
DLE = 0x10  # ^P  constituent pointer


def _text(path: Path) -> str:
    """Read a SAIL data file, mapping control-byte prefixes to ASCII markers."""
    raw = Path(path).read_bytes()
    raw = raw.replace(bytes([BS]), b"H")       # ^H#### -> H####
    raw = raw.replace(bytes([CAN]), b"@X@")    # ^X (POS recast)
    raw = raw.replace(bytes([DLE]), b"@P@")    # ^P (constituent pointer)
    return raw.decode("latin-1")


def _unit(tok: str) -> str | None:
    """Normalise a unit token; NIL -> None, otherwise the token as-is."""
    tok = tok.strip()
    return None if tok == "NIL" or tok == "" else tok


def _nonempty_lines(path: Path):
    for line in _text(path).splitlines():
        s = line.rstrip("\n")
        if s.strip():
            yield s


# --- dictionary & word normalisation ---------------------------------------

@dataclass
class DictEntry:
    kind: str          # "pos" or "canon"
    value: str         # the POS tag, or the (possibly multi-token) rewrite
    tokens: list       # value split into tokens (for canon rewrites)


def load_dictio(path) -> dict[str, DictEntry]:
    """dictio: WORD\\t\\t\\tVALUE. Value is a lowercase POS or an uppercase rewrite."""
    out: dict[str, DictEntry] = {}
    for line in _nonempty_lines(Path(path)):
        parts = line.split("\t")
        word = parts[0]
        value = parts[-1].strip()
        if not word or not value:
            continue
        kind = "pos" if value.islower() else "canon"
        out[word] = DictEntry(kind=kind, value=value, tokens=value.split())
    return out


def load_synonyms(path) -> dict[str, str]:
    """synonm.alf: (WORD CANONICAL)."""
    out: dict[str, str] = {}
    for line in _nonempty_lines(Path(path)):
        toks = line.strip().strip("()").split()
        if len(toks) >= 2:
            out[toks[0]] = toks[1]
    return out


def load_irregular(path) -> dict[str, list]:
    """irreg.alf: (WORD EXPANSION...)."""
    out: dict[str, list] = {}
    for line in _nonempty_lines(Path(path)):
        toks = line.strip().strip("()").split()
        if toks:
            out[toks[0]] = toks[1:]
    return out


def load_wordset(path) -> set:
    """flags.alf / startr.alf / stoppr.alf: one bare word per line."""
    return {line.strip() for line in _nonempty_lines(Path(path))}


# --- affix / idiom tables ---------------------------------------------------

@dataclass
class Affix:
    affix: str
    base_pos: str | None      # POS the base word must have (suffix/prefix table)
    action: list = field(default_factory=list)  # tokens; may hold @X@/word/tense


def load_suffix_alf(path) -> list[Affix]:
    """suffix.alf: (SUFFIX [REPLACEMENT])."""
    out: list[Affix] = []
    for line in _nonempty_lines(Path(path)):
        toks = line.strip().strip("()").split()
        if toks:
            out.append(Affix(affix=toks[0], base_pos=None, action=toks[1:]))
    return out


def load_affix_table(path) -> list[Affix]:
    """suffix / prefix: tab-aligned  AFFIX \\t BASE-POS [\\t\\t] ACTION."""
    out: list[Affix] = []
    for line in _nonempty_lines(Path(path)):
        parts = [p for p in line.split("\t") if p.strip()]
        if not parts:
            continue
        affix = parts[0].strip()
        base_pos = parts[1].strip() if len(parts) > 1 else None
        action = parts[2].split() if len(parts) > 2 else []
        out.append(Affix(affix=affix, base_pos=base_pos, action=action))
    return out


def load_idioms(path) -> list[tuple]:
    """idiom.alf: ((PHRASE...) REPLACEMENT...). Empty replacement = delete."""
    out: list[tuple] = []
    for line in _nonempty_lines(Path(path)):
        m = re.match(r"\(\((.*?)\)(.*)\)\s*$", line.strip())
        if not m:
            continue
        phrase = tuple(m.group(1).split())
        replacement = m.group(2).split()
        out.append((phrase, replacement))
    return out


def load_multi(path) -> list[tuple]:
    """multi: POS-sequence \\t action. Returns (lhs_tokens, rhs_tokens)."""
    out: list[tuple] = []
    for line in _nonempty_lines(Path(path)):
        parts = [p for p in line.split("\t") if p.strip()]
        if len(parts) >= 2:
            out.append((parts[0].split(), parts[1].split()))
    return out


# --- pattern tables ---------------------------------------------------------

@dataclass
class SimplePattern:
    words: tuple      # sequence of (truncated) canonical words
    target: str       # unit id (H#### / P####)


@dataclass
class CompoundPattern:
    units: tuple      # sequence of unit ids
    target: str


def load_spats(path) -> list[SimplePattern]:
    """spats.sel: ((WORDS...) TARGET) — 3549 simple sentence patterns."""
    out: list[SimplePattern] = []
    for line in _nonempty_lines(Path(path)):
        m = re.match(r"\(\((.*?)\)\s*(\S+)\)\s*$", line.strip())
        if not m:
            continue
        words = tuple(m.group(1).split())
        target = _unit(m.group(2))
        if target:
            out.append(SimplePattern(words=words, target=target))
    return out


def load_cpats(path) -> list[CompoundPattern]:
    """cpats.sel: ((UNIT...) TARGET) — 1196 compound patterns over units."""
    out: list[CompoundPattern] = []
    for line in _nonempty_lines(Path(path)):
        m = re.match(r"\(\((.*?)\)\s*(\S+)\)\s*$", line.strip())
        if not m:
            continue
        units = tuple(u for u in (_unit(t) for t in m.group(1).split()) if u)
        target = _unit(m.group(2))
        if target:
            out.append(CompoundPattern(units=units, target=target))
    return out


def load_unit_pairs(path) -> list[tuple]:
    """negate.pat / famly.pat / same.pat: (UNIT UNIT) -> (a, b) with None for NIL."""
    out: list[tuple] = []
    for line in _nonempty_lines(Path(path)):
        toks = line.strip().strip("()").split()
        if len(toks) >= 2:
            out.append((_unit(toks[0]), _unit(toks[1])))
    return out


def load_unit_list(path) -> list[str]:
    """filler.pat: one bare unit per line."""
    return [u for u in (_unit(line.strip()) for line in _nonempty_lines(Path(path))) if u]


def load_nearby(path) -> list[tuple]:
    """nearby.key: (A B) (A B) ... on one line — keyboard neighbour pairs."""
    text = _text(Path(path))
    return [(a, b) for a, b in re.findall(r"\(([A-Z]) ([A-Z])\)", text)]


# --- bundle ----------------------------------------------------------------

@dataclass
class Lexicon:
    """All lexical/pattern data PARRY needs, loaded from a source directory."""

    dictio: dict
    synonyms: dict
    irregular: dict
    idioms: list
    suffix_alf: list
    suffix: list
    prefix: list
    multi: list
    spats: list
    cpats: list
    negate: list
    famly: list
    same: list
    filler: list
    flags: set
    startr: set
    stoppr: set
    nearby: list

    @classmethod
    def load(cls, src_dir=None) -> Lexicon:
        d = Path(src_dir) if src_dir is not None else DATA_DIR
        return cls(
            dictio=load_dictio(d / "dictio"),
            synonyms=load_synonyms(d / "synonm.alf"),
            irregular=load_irregular(d / "irreg.alf"),
            idioms=load_idioms(d / "idiom.alf"),
            suffix_alf=load_suffix_alf(d / "suffix.alf"),
            suffix=load_affix_table(d / "suffix"),
            prefix=load_affix_table(d / "prefix"),
            multi=load_multi(d / "multi"),
            spats=load_spats(d / "spats.sel"),
            cpats=load_cpats(d / "cpats.sel"),
            negate=load_unit_pairs(d / "negate.pat"),
            famly=load_unit_pairs(d / "famly.pat"),
            same=load_unit_pairs(d / "same.pat"),
            filler=load_unit_list(d / "filler.pat"),
            flags=load_wordset(d / "flags.alf"),
            startr=load_wordset(d / "startr.alf"),
            stoppr=load_wordset(d / "stoppr.alf"),
            nearby=load_nearby(d / "nearby.key"),
        )
