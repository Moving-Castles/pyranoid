"""PARRY's linguistic front-end: turn a typed sentence into semantic unit(s).

The original front-end (front.lap) survives only as compiled PDP-10 assembly, so
this is a reconstruction of its documented pipeline (all.doc's FRONT section)
operating on PARRY's real data tables (dictio, synonm.alf, spats.sel, cpats.sel,
idiom.alf, irreg.alf, suffix). The steps:

  1. tokenise and upper-case
  2. expand irregulars/contractions (CAN'T -> CAN NOT)
  3. canonicalise each word via the dictionary and synonyms (ABNORMAL -> ODD)
  4. apply idiom substitutions over the word sequence (COSA NOSTRA -> MAFIA)
  5. truncate words to 5 chars (patterns are stored truncated: NUMBR, BANAN)
  6. match against simple patterns (spats) as ordered subsequences
  7. reduce the resulting unit sequence with compound patterns (cpats)

The final unit is an H-unit that indexes PARRY's memory (PDAT). P-units produced
by step 6 are intermediate constituents; they yield a response only if a compound
pattern combines them into an H-unit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pyranoid.data import Lexicon

WORDCHARS = re.compile(r"[A-Z0-9']+")
TRUNC = 5


@dataclass
class Analysis:
    """Result of analysing one input sentence."""

    raw: str
    words: list         # canonicalised, truncated tokens
    units: list         # unit ids after spats+cpats reduction
    unit: str | None    # the final chosen H-unit (or None = NOPATTERN)
    matched_pattern: tuple | None = None


class FrontEnd:
    def __init__(self, lex: Lexicon):
        self.lex = lex
        # index simple patterns by first word for a faster scan
        self._spats_by_first: dict[str, list] = {}
        for sp in lex.spats:
            if sp.words:
                self._spats_by_first.setdefault(sp.words[0], []).append(sp)
        # compound patterns keyed by first unit
        self._cpats_by_first: dict[str, list] = {}
        for cp in lex.cpats:
            if cp.units:
                self._cpats_by_first.setdefault(cp.units[0], []).append(cp)

    # -- word canonicalisation ---------------------------------------------

    def _canon_word(self, w: str) -> list[str]:
        """Canonicalise a single surface word into one or more canonical words."""
        # irregulars / contractions first (may expand to several words)
        if w in self.lex.irregular:
            out: list[str] = []
            for x in self.lex.irregular[w]:
                out.extend(self._canon_word(x))
            return out
        # dictionary rewrite (canon) -> possibly multi-word; POS entries pass through
        de = self.lex.dictio.get(w)
        if de is not None and de.kind == "canon" and de.tokens != [w]:
            out = []
            for x in de.tokens:
                out.extend(self._canon_word(x) if x != w else [x])
            return out
        # synonym mapping (single word), applied to a fixpoint
        seen = set()
        cur = w
        while cur in self.lex.synonyms and cur not in seen:
            seen.add(cur)
            nxt = self.lex.synonyms[cur]
            if nxt == cur:
                break
            cur = nxt
        return [cur]

    def canonise(self, text: str) -> list[str]:
        tokens = WORDCHARS.findall(text.upper())
        tokens = self._apply_idioms(tokens)          # surface-form idioms
        words: list[str] = []
        for t in tokens:
            words.extend(self._canon_word(t))
        words = self._apply_idioms(words)            # canonical-form idioms
        return [w[:TRUNC] for w in words]

    def _apply_idioms(self, words: list[str]) -> list[str]:
        """Replace idiom phrases (longest first) with their canonical form."""
        idioms = sorted(self.lex.idioms, key=lambda p: -len(p[0]))
        changed = True
        while changed:
            changed = False
            for phrase, repl in idioms:
                n = len(phrase)
                if n == 0:
                    continue
                for i in range(len(words) - n + 1):
                    if tuple(words[i:i + n]) == phrase:
                        words = words[:i] + list(repl) + words[i + n:]
                        changed = True
                        break
                if changed:
                    break
        return words

    # -- pattern matching ---------------------------------------------------

    @staticmethod
    def _is_subsequence(pat: tuple, words: list) -> bool:
        """True if pat occurs as an ordered (not necessarily contiguous) subsequence."""
        it = iter(words)
        return all(any(p == w for w in it) for p in pat)

    def match_spats(self, words: list[str]) -> str | None:
        """Best simple-pattern match: the most specific (longest) subsequence."""
        best = None
        best_len = 0
        # candidate patterns are those whose first word appears in the input
        wordset = set(words)
        for first in wordset:
            for sp in self._spats_by_first.get(first, ()):
                if len(sp.words) > best_len and self._is_subsequence(sp.words, words):
                    best, best_len = sp, len(sp.words)
        return best.target if best else None

    def reduce_cpats(self, units: list[str]) -> list[str]:
        """Combine adjacent units via compound patterns until stable."""
        changed = True
        while changed and len(units) > 1:
            changed = False
            for cp in self.lex.cpats:
                n = len(cp.units)
                for i in range(len(units) - n + 1):
                    if tuple(units[i:i + n]) == cp.units:
                        units = units[:i] + [cp.target] + units[i + n:]
                        changed = True
                        break
                if changed:
                    break
        return units

    # -- top level ----------------------------------------------------------

    def analyse(self, text: str) -> Analysis:
        words = self.canonise(text)
        # For a first reconstruction we match one unit over the whole sentence,
        # then attempt compound reduction against any earlier context unit.
        unit = self.match_spats(words)
        units = [unit] if unit else []
        units = self.reduce_cpats(units) if len(units) > 1 else units
        final = None
        for u in units:
            if u and u.startswith("H"):
                final = u
        if final is None and unit and unit.startswith("H"):
            final = unit
        return Analysis(raw=text, words=words, units=units, unit=final,
                        matched_pattern=None)
