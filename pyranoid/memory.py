"""Response selection and dialogue memory.

Bridges the pattern front-end and the recovered PDAT memory:

  * pdatb maps group names and concepts to units:
      (DEFPROP HELLO  H0042 IND)   -> group HELLO's responses live in unit H0042
      (DEFPROP REASON H0030 UNIT)  -> concept REASON is unit H0030
  * a belief unit (#B) points via RESP to a response unit (#E) whose NORMAL list
    holds the candidate sentences.
  * CHOOSE cycles through a unit's sentences; a unit flagged EXH switches to the
    "I already told you" exhaust responses once its sentences are used up
    (opar3 CHOOSE). Others simply repeat.
  * anaphora: after answering from a unit, its ANAPH map becomes the current
    !ANAPHLIST, so a follow-up "why?" / "who?" resolves to the right unit.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from pyranoid.data import _text
from pyranoid.pdat import Memory, ResponseUnit

_DEFPROP = re.compile(r"\(DEFPROP\s+(\S+)\s+(\S+)\s+(IND|UNIT)\)")


class Dialogue:
    """Selects PARRY's next utterance from the recovered memory."""

    def __init__(self, mem: Memory, pdatb_path, rng: random.Random | None = None):
        self.mem = mem
        self.rng = rng or random.Random()
        self.group_unit: dict[str, str] = {}   # IND:  group   -> unit id
        self.concept_unit: dict[str, str] = {}  # UNIT: concept -> unit id
        self.unit_concept: dict[str, str] = {}  # reverse of the above
        self._load_pdatb(pdatb_path)

        self.used: dict[str, set] = {}          # unit -> indices already said
        self.anaph: dict[str, str] = {}         # current !ANAPHLIST
        self.last_unit: str | None = None
        self.exhausted_now = False              # set when a set runs out (EXH)

    # -- pdatb: group/concept -> unit --------------------------------------

    def _load_pdatb(self, path) -> None:
        for line in _text(Path(path)).splitlines():
            m = _DEFPROP.search(line)
            if not m:
                continue
            a, b, prop = m.group(1), m.group(2), m.group(3)
            if prop == "IND":
                self.group_unit[a] = b        # group name -> unit
            else:  # UNIT: either (concept unit) or (unit concept)
                if a.startswith("H"):
                    self.unit_concept[a] = b
                    self.concept_unit.setdefault(b, a)
                else:
                    self.concept_unit[a] = b
                    self.unit_concept.setdefault(b, a)

    # -- low-level response cycling ----------------------------------------

    def _unit_of_group(self, name: str) -> str | None:
        """Resolve a group/concept name to a unit id (IND then UNIT)."""
        if name in self.mem.beliefs or name in self.mem.responses:
            return name
        return self.group_unit.get(name) or self.concept_unit.get(name)

    def _response_unit(self, unit: str) -> ResponseUnit | None:
        """Get the #E response unit for a belief/#E/group id."""
        if unit in self.mem.responses:
            return self.mem.responses[unit]
        b = self.mem.beliefs.get(unit)
        if b and b.resp and b.resp in self.mem.responses:
            return self.mem.responses[b.resp]
        return None

    def _pick(self, ru: ResponseUnit) -> str | None:
        """Pick and consume a sentence (SELSENTENCE).

        Consumption is destructive within an interview: each sentence is said at
        most once. A unit flagged EXH is read strictly in listed order; others
        pick at random. When the pool is emptied the unit is exhausted and the
        caller falls back to the EXHAUST responses.
        """
        spoken = [r.words for r in ru.normal if r.words]  # skip tag-only entries
        if not spoken:
            self.exhausted_now = True
            return None
        used = self.used.setdefault(ru.name, set())
        remaining = [i for i in range(len(spoken)) if i not in used]
        if not remaining:
            self.exhausted_now = True
            return None
        idx = remaining[0] if ru.exhaust else self.rng.choice(remaining)
        used.add(idx)
        return spoken[idx]

    # -- public selection ---------------------------------------------------

    def choose(self, name: str) -> str | None:
        """CHOOSE: say something from a named group / concept / unit."""
        self.exhausted_now = False
        unit = self._unit_of_group(name)
        if unit is None:
            return None
        ru = self._response_unit(unit)
        if ru is None:
            return None
        text = self._pick(ru)
        if text is None and self.exhausted_now:
            # opar3: exhausted set -> use the EXHAUST responses, then give up
            eu = self._response_unit(self.group_unit.get("EXHAUST", ""))
            if eu is not None:
                text = self._pick(eu)
        if text is not None:
            self._remember(unit, ru)
        return text

    def answer_unit(self, unit: str) -> str | None:
        """Answer a matched belief unit by following its RESP chain."""
        self.exhausted_now = False
        ru = self._response_unit(unit)
        if ru is None:
            return None
        text = self._pick(ru)
        if text is None and self.exhausted_now:
            eu = self._response_unit(self.group_unit.get("EXHAUST", ""))
            if eu is not None:
                text = self._pick(eu)
        if text is not None:
            self._remember(unit, ru)
        return text

    def _remember(self, unit: str, ru: ResponseUnit) -> None:
        """Record the anaphora context set up by the unit just spoken."""
        self.last_unit = unit
        if ru.anaph:
            self.anaph = dict(ru.anaph)

    # -- anaphora -----------------------------------------------------------

    def resolve_anaphor(self, word: str) -> str | None:
        """Resolve a follow-up interrogative against the current !ANAPHLIST."""
        target = self.anaph.get(word)
        if target is None:
            return None
        # target may be a unit id or a concept name
        if target in self.mem.beliefs or target in self.mem.responses:
            return target
        return self.concept_unit.get(target, target)
