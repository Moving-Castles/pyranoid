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
        # suffix rules, longest suffix first (DE_SUFFIX)
        self._suffixes = sorted(lex.suffix + lex.suffix_alf,
                                key=lambda a: -len(a.affix))
        # negation map: matched unit -> its opposite-meaning unit (negate.pat)
        self.negate_map = {a: b for a, b in lex.negate if a and b}
        # words that flag a fragment as negated (flags.alf has NOT)
        self._recognised = set(lex.dictio) | set(lex.synonyms) | set(lex.irregular)

    def _is_recognised(self, w: str) -> bool:
        return w in self._recognised

    def _de_suffix(self, w: str) -> list[str] | None:
        """Strip a known suffix to reach a recognised root (front.lap DE_SUFFIX).

        Only fires on words not otherwise recognised, so it is a last resort.
        Replacement-word actions (N'T -> NOT, 'S -> IS, 'D -> WOULD) are applied;
        part-of-speech recasts (^X…) and tense tags are dropped for matching.
        """
        for suf in self._suffixes:
            aff = suf.affix
            if len(w) > len(aff) + 1 and w.endswith(aff):
                root = w[: len(w) - len(aff)]
                if self._is_recognised(root):
                    extra = [a for a in suf.action
                             if a.isupper() and not a.startswith("@X@")]
                    return [root, *extra]
        return None

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
        # last resort: strip a suffix to reach a recognised root
        if cur == w and not self._is_recognised(w):
            stripped = self._de_suffix(w)
            if stripped is not None:
                out = []
                for x in stripped:
                    out.extend(self._canon_word(x) if x != w else [x])
                return out
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

    def segment(self, words: list[str]) -> list[list[str]]:
        """Split a canonicalised sentence into fragments (front.lap SEGMENT).

        A word in startr.alf begins a new fragment; a word in stoppr.alf ends the
        current one, dropping the framing verb ("do you THINK the mafia..." keeps
        "the mafia..."). Returns the list of non-empty fragments.
        """
        frags: list[list[str]] = []
        cur: list[str] = []
        for w in words:
            if w in self.lex.stoppr:
                cur = []                      # discard the framing clause so far
                continue
            if w in self.lex.startr and cur:
                frags.append(cur)
                cur = [w]
            else:
                cur.append(w)
        if cur:
            frags.append(cur)
        return frags or [words]

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
        # Match each fragment, then reduce the unit sequence with compound
        # patterns. Fall back to a whole-sentence match if fragmenting finds
        # nothing (keeps single-clause questions matching as before).
        frags = self.segment(words)
        units = [u for u in (self.match_spats(f) for f in frags) if u]
        if not units:
            whole = self.match_spats(words)
            units = [whole] if whole else []
        units = self.reduce_cpats(units) if len(units) > 1 else units
        final = None
        for u in units:
            if u and u.startswith("H"):
                final = u  # last H-unit wins (closest to sentence end)
        if final is None and units and units[-1] and units[-1].startswith("H"):
            final = units[-1]
        # Negation: if the sentence carries NOT and the matched unit has an
        # opposite-meaning unit (negate.pat), flip to it.
        if final is not None and "NOT" in words and final in self.negate_map:
            final = self.negate_map[final]
        return Analysis(raw=text, words=words, units=units, unit=final,
                        matched_pattern=None)
