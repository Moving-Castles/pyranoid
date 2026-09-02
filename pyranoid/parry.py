"""PARRY — the top-level agent tying the front-end, model, and memory together.

Implements a faithful reconstruction of the REACT control loop (pmem4 REACT,
per the ported spec): per turn it canonicalises the input, tries an in-memory
answer (with anaphora), runs the affect/flare/delusion model, lets an emotion-
driven intention pre-empt the literal answer, and otherwise falls back through
keyword and miscellaneous replies — then decays the emotions.

Faithful in structure and data (Colby's real patterns, memory, and affect
dynamics); the pattern front-end and some of REACT's glue are reconstructed
because the original front.lap survives only as compiled assembly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from pyranoid import parry_data as D
from pyranoid.data import DATA_DIR, Lexicon
from pyranoid.frontend import FrontEnd
from pyranoid.memory import Dialogue
from pyranoid.model import Model
from pyranoid.pdat import load_pdat

# Words that end an interview / greet, detected before pattern matching.
_GOODBYE = {"BYE", "GOODBYE", "GOODBY"}
_GREETING = {"HELLO", "HI"}
_SWEAR = {"SHIT", "FUCK", "DAMN", "BASTARD", "ASSHOLE"}
# input CLASS -> reply group under strong feeling (pmem5 STRONGFEEL)
_CLASS_GROUP = {
    "INSULT": "ANGER", "WEAKINSULT": "PERS", "COMPLEMENT": "DISTANCE",
    "SENSATTITUDE": "SENSREPLIES", "CRAZY": "HOSTILEREPLIES", "THREAT": "PANIC",
    "DISBELIEF": "BELIEVEREPLIES", "APOLOGY": "ACCUSE", "LYING": "BELIEVEREPLIES",
}


@dataclass
class Turn:
    """Diagnostics for one exchange (mirrors the DIA trace)."""

    user: str
    reply: str
    unit: str | None = None
    trace: str = ""            # OK / SPECIALANAPH / KEYWORD / NO_PATTERN / INTENT ...
    intent: str | None = None
    affect: dict = field(default_factory=dict)


class Parry:
    def __init__(self, src_dir=None, pdat=None, pdatb=None,
                 version="STRONG", seed=None):
        # Default to the data bundled inside the package, so the port is
        # self-contained; callers may override with explicit paths.
        src_dir = Path(src_dir) if src_dir else DATA_DIR
        pdat = Path(pdat) if pdat else DATA_DIR / "pdatz.txt"
        pdatb = Path(pdatb) if pdatb else DATA_DIR / "pdatb"
        self.lex = Lexicon.load(src_dir)
        self.frontend = FrontEnd(self.lex)
        self.mem = load_pdat(pdat)
        rng = random.Random(seed)
        self.dialogue = Dialogue(self.mem, pdatb, rng=rng)
        self.model = Model(version=version)
        self.ended = False
        self.turns: list[Turn] = []
        self._w2flare = D.word_to_flare()
        self._w2sens = D.word_to_sensitive()

    # -- helpers ------------------------------------------------------------

    def greeting(self) -> str:
        return self.dialogue.choose("HELLO") or "GOOD AFTERNOON. HOW ARE YOU?"

    @staticmethod
    def _is_question(text: str, words: list[str]) -> bool:
        if "?" in text:
            return True
        q = {"HOW", "WHO", "WHOM", "WHAT", "WHEN", "WHERE", "WHY", "WHICH",
             "BE", "DO", "DID", "CAN", "WILL", "ARE", "IS", "HAVE"}
        return bool(words) and words[0] in q

    def _scan_affect(self, words: list[str]) -> None:
        """Set emotion jumps from flare / delusion / sensitive words (SKEYWD/AFFECT)."""
        # delusion words push fear hard
        strong = any(w in D.DELUSION_NOUNS_STRONG or w in D.DELUSION_VERBS_STRONG
                     for w in words)
        if any(w == "MAFIA" for w in words) or strong:
            self.model.delusion_reference(found_strong=strong)
        else:
            self.model.flare_reference(words)
        # sensitive topics nudge anger a little (pmem5)
        if any(w in self._w2sens for w in words):
            self.model.ajump = max(self.model.ajump or 0.0, 0.2)

    # -- the turn -----------------------------------------------------------

    def respond(self, text: str) -> str:
        self.dialogue.exhausted_now = False
        analysis = self.frontend.analyse(text)
        words = analysis.words
        is_q = self._is_question(text, words)
        trace = "NO_PATTERN"
        intent = None
        reactto: str | None = None      # the literal in-memory answer

        # Step 2 — CHECKINPUT specials (swearing / bye / greeting)
        special = None
        if any(w in _SWEAR for w in words):
            self.model.ajump = 0.6
            special, trace = "SWEARING", "INTENT"
        elif any(w in _GOODBYE for w in words):
            self.ended = True
            special, trace = "BYE", "OK"
        elif words and words[0] in _GREETING and analysis.unit is None:
            special, trace = "HELLO", "OK"

        # Step 3 — anaphora, then direct in-memory answer
        if special is None:
            anaph_target = None
            if len(words) <= 2:
                for w in words:
                    anaph_target = self.dialogue.resolve_anaphor(w)
                    if anaph_target:
                        break
            if anaph_target:
                reactto, trace = anaph_target, "SPECIALANAPH"
            elif analysis.unit and analysis.unit in self.mem.beliefs:
                reactto, trace = analysis.unit, "OK"

        # Step 5 — affect model runs every turn
        self._scan_affect(words)
        self.model.raise_affect()
        intent = self.model.paranoid_intent()

        # Step 5b — an emotion-driven intention can pre-empt the literal answer
        reply = None
        unit_used = None
        if special is not None:
            reply = self.dialogue.choose(special)
            unit_used = special
        elif intent is not None:
            group = self._intent_group(analysis, is_q)
            if group:
                reply = self.dialogue.choose(group)
                unit_used, trace = group, "INTENT"

        # Step 5c — otherwise the literal answer
        if reply is None and reactto is not None:
            reply = self.dialogue.answer_unit(reactto)
            unit_used = reactto
            if self.dialogue.exhausted_now:
                reply = self.dialogue.choose("EXHAUST") or reply

        # Step 4 — keyword fallback (delusion/flare/topic scan)
        if reply is None and not self.model.delflag:
            kw = self._keyword_fallback(words)
            if kw:
                reply, unit_used, trace = kw, None, "KEYWORD"

        # Step 6 — miscellaneous punt
        if reply is None:
            group = "QREPLIES" if is_q else "SREPLIES"
            reply = self.dialogue.choose(group) or "I DON'T KNOW."
            unit_used, trace = group, "NO_PATTERN"

        # Step 9 — decay emotions, record the turn
        self.model.modify_vars()
        turn = Turn(user=text, reply=reply, unit=unit_used, trace=trace,
                    intent=intent, affect=self.model.affect.snapshot())
        self.turns.append(turn)
        return reply

    # -- intent / fallback helpers -----------------------------------------

    def _intent_group(self, analysis, is_q: bool) -> str | None:
        """Map the current intention + input class to a reply group (STRONGFEEL)."""
        # class of the matched unit, if any
        cls = None
        if analysis.unit and analysis.unit in self.mem.beliefs:
            cls = self.mem.beliefs[analysis.unit].fields.get("CLASS")
        if cls and cls in _CLASS_GROUP:
            return _CLASS_GROUP[cls]
        # otherwise diffuse anger/fear mode, deferring on flare/feeling topics
        topic = self.model.topic
        grp = self.model.anger_fear_mode(topic)
        if grp == "EXIT":
            self.ended = True
        elif grp in ("AFRAID", "THREATQ") and is_q:
            grp = "THREATQ"
        return grp

    def _keyword_fallback(self, words: list[str]) -> str | None:
        """SKEYWD: delusion words, then flare words, then topic keyword scan."""
        # delusion already handled in _scan_affect via delusion_reference;
        # here, if a flare is active, tell its story line
        if self.model.flare != "INIT":
            story = D.STORY.get(self.model.flare)
            if story:
                return self.dialogue.answer_unit(story[0])
        # topic keyword scan (KEYWD): match a topic word -> its story
        w2t = D.word_to_topic()
        for w in words:
            t = w2t.get(w)
            if t and t in D.STORY:
                return self.dialogue.answer_unit(D.STORY[t][0])
        return None
