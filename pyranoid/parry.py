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
from pyranoid.beliefs import BeliefBase
from pyranoid.data import DATA_DIR, Lexicon
from pyranoid.frontend import FrontEnd
from pyranoid.inference import Inference
from pyranoid.memory import Dialogue
from pyranoid.model import Model
from pyranoid.pdat import load_pdat

# Words that end an interview / greet, detected before pattern matching.
_GOODBYE = {"BYE", "GOODBYE", "GOODBY"}
_GREETING = {"HELLO", "HI"}
_SWEAR = {"SHIT", "FUCK", "DAMN", "BASTARD", "ASSHOLE"}

# input CLASS -> reply group under strong feeling (pmem5 STRONGFEEL)
_STRONGFEEL_GROUP = {
    "INSULT": "ANGER", "WEAKINSULT": "PERS", "COMPLEMENT": "DISTANCE",
    "SENSATTITUDE": "SENSREPLIES", "CRAZY": "HOSTILEREPLIES", "THREAT": "PANIC",
    "DISBELIEF": "BELIEVEREPLIES", "APOLOGY": "ACCUSE", "LYING": "BELIEVEREPLIES",
}
# input CLASS -> reply group under paranoia (pmem5 PPARANOIA)
_PARANOIA_GROUP = {
    "INSULT": "PANGER", "CRAZY": "AVOIDANCE", "THREAT": "PANIC", "ATTACK": "LIE",
    "FEELINGS": "LIE", "WEAKINSULT": "PPERS", "COMPLEMENT": "PDISTANCE",
    "DISBELIEF": "PBELIEVEREPLIES", "APOLOGY": "PACCUSE",
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
        self.beliefs = BeliefBase.load()
        self.inference = Inference(self.beliefs, self.model)
        self.ended = False
        self.exhaust_count = 0
        self.inputno = 0
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
        # DELCHECK/DELREF: a delusion noun/verb (MAFIA GUN DEATH CHIEF KILL SPY)
        # triggers the delusion; ambiguous words (BEAT HATE) only at high mistrust.
        delusion = set(D.DELUSION_NOUNS) | set(D.DELUSION_VERBS)
        strong_set = set(D.DELUSION_NOUNS_STRONG) | set(D.DELUSION_VERBS_STRONG)
        found = None
        found_strong = False
        for w in words:
            if w in delusion:
                found, found_strong = w, w in strong_set
                break
            if w in D.DELUSION_AMBIG and self.model.affect.mistrust > 10:
                found = w
                break
        if found is not None:
            self.model.delusion_reference(found_strong=found_strong)
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

        # Step 5a — INFERENCE: the matched unit asserts beliefs about the doctor
        # / self, which fire EMOTE jumps; flare/delusion words add their own.
        self.inputno += 1
        self._scan_affect(words)
        self.inference.infer(analysis.unit, self._context(analysis))

        # Step 5b — AFFECT: apply jumps, then set the forced intention.
        forced = self._affect(analysis)

        # Step 5c — DOINTENT: the winning intention may pre-empt the answer.
        reply = None
        unit_used = None
        intent = self.inference.winning_intent(forced)
        if special is not None:
            reply = self.dialogue.choose(special)
            unit_used = special
        elif intent is not None:
            reply = self._do_intent(intent, analysis, is_q)
            if reply is not None:
                unit_used, trace = intent, "INTENT"

        # Step 5d — otherwise the literal answer
        if reply is None and reactto is not None:
            reply = self.dialogue.answer_unit(reactto)
            unit_used = reactto
            if reply is None and self.dialogue.exhausted_now:
                reply = self._exhaustion_recovery()
                unit_used, trace = "EXHAUST", "INTENT"

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

    # -- AFFECT / DOINTENT -------------------------------------------------

    def _context(self, analysis) -> dict:
        """Runtime variables the IF-rule antecedents read (MEASURE/GREATERP/EQ)."""
        a = self.model.affect
        return {
            "FEAR": a.fear, "ANGER": a.anger, "MISTRUST": a.mistrust, "HURT": a.hurt,
            "INPUTNO": self.inputno, "REPEATNO": 0, "NEWTOPICNO": 0,
            "MISCNO": 0, "SPECFNRA": 0, "DELNO": 0,
            "STOPIC": self.model.topic, "DELFLAG": self.model.delflag,
        }

    def _unit_class(self, unit: str | None) -> str | None:
        """The CLASS tag of a matched unit (belief unit, else its response unit)."""
        if not unit:
            return None
        b = self.mem.beliefs.get(unit)
        if b and "CLASS" in b.fields:
            return b.fields["CLASS"]
        ru = self.dialogue._response_unit(unit)
        if ru and "CLASS" in ru.fields:
            return ru.fields["CLASS"]
        return None

    def _affect(self, analysis) -> str | None:
        """AFFECT (pmem5): apply jumps, force the emotion-driven intention."""
        a = self.model.affect
        if any(w in self._w2sens for w in analysis.words):
            self.model.ajump = max(self.model.ajump or 0.0, 0.2)
        self.model.raise_affect()

        forced = None
        if a.fear > 18 or a.anger > 18.8:
            self.inference.add_to_intent("PEXIT2", 10)
        strong = self.model.version == "STRONG" and (
            a.hurt > 7 or (self.model.hjump is not None and self.model.hjump >= 0.1))
        mild = self.model.version == "MILD" and a.hurt > 8
        if strong or mild:
            self.inference.add_to_intent("PPARANOIA", 5)
            self._paranoia_project()
            forced = "PPARANOIA"
        elif (
            (self.model.fjump is not None and self.model.fjump >= 0.01)
            or (self.model.ajump is not None and self.model.ajump >= 0.01)
            or a.fear > 14 or a.anger > 14 or self.model.topic == "STRONGFEELINGS"
        ):
            self.inference.add_to_intent("PSTRONGFEEL", 5)
            forced = "PSTRONGFEEL"
        return forced

    def _paranoia_project(self) -> None:
        """PARANOIA (pmem5): project self-shame onto distrust of the doctor."""
        project = {"LYING": "*DHONEST", "LOSER": "*DSOCIABLE",
                   "CRAZY": "DABNORMAL", "DUMB": "*DCHELP"}
        self.inference.assert2("*DTRUSTWORTHY")
        for src in self.inference.parbel:
            if src in project:
                self.inference.assert2(project[src])
        self.inference.parbel = []

    def _do_intent(self, intent: str, analysis, is_q: bool) -> str | None:
        """DOINTENT dispatch: run the chosen intention's routine (pmem5)."""
        cls = self._unit_class(analysis.unit)
        a = self.model.affect

        if intent == "PPARANOIA":
            if a.hurt > 10:
                a.hurt = 10 + (a.hurt - 10) * 3 / 5
            group = _PARANOIA_GROUP.get(cls)
            if group is None:
                group = self._diffuse_mode(is_q, paranoid=True)
            self.inference.add_to_intent("PEXIT", 1)
            return self.dialogue.choose(group)

        if intent == "PSTRONGFEEL":
            group = _STRONGFEEL_GROUP.get(cls)
            if group is None and (a.anger > 14 or a.fear > 14):
                group = self._diffuse_mode(is_q, paranoid=False)
            return self.dialogue.choose(group) if group else None

        if intent in ("PEXIT", "PEXIT2"):
            if a.anger > 9:
                group = "MADEXIT"
            elif a.fear > 9:
                group = "FEAREXIT"
            else:
                group = "EXIT"
            self.ended = True
            return self.dialogue.choose(group)

        if intent == "PMAFIA":
            group = "PANIC" if a.fear > 10 else "PROBE"
            self.inference.add_to_intent("PMAFIA", -2)
            return self.dialogue.choose(group)

        if intent == "PGAMES":
            self.inference.add_to_intent("PGAMES", -2)
            return self.dialogue.choose("GAMES")
        if intent == "PFACTS":
            self.inference.add_to_intent("PFACTS", -2)
            return self.dialogue.choose("MOVEON")
        if intent == "PSELF":
            self.inference.add_to_intent("PSELF", -3)
            return self.dialogue.choose("IYOUME")
        # PINTERACT / PHELP / PTELL / PCONFIRM: no direct utterance here — let the
        # literal answer stand (PARRY keeps interviewing) but bootstrap PHELP.
        if intent == "PINTERACT" and self.model.flare == "INIT":
            self.inference.add_to_intent("PHELP", 5)
        return None

    def _diffuse_mode(self, is_q: bool, paranoid: bool) -> str:
        """FEARMODE/ANGERMODE: diffuse high emotion into a reply group."""
        a = self.model.affect
        if a.fear >= 14:
            if a.fear > 18.4:
                self.ended = True
                return "EXIT"
            return "THREATQ" if is_q else "AFRAID"
        return "ANGER" if a.anger > 17.5 else "HOSTILEREPLIES"

    def _exhaustion_recovery(self) -> str | None:
        """REACT3: a set ran out — tell the topic's story, else EXHAUSTER.

        EXHAUSTER counts exhaustions, nudges anger, and ends the interview with
        MADEXIT on the ninth; otherwise fall back to the "I already told you"
        EXHAUST responses (pmem2 EXHAUSTER, opar3 CHOOSE 'EXHAUST).
        """
        story = D.STORY.get(self.model.topic) or D.STORY.get(self.model.flare)
        if story:
            for u in story:
                r = self.dialogue.answer_unit(u)
                if r:
                    return r
        self.exhaust_count += 1
        self.model.ajump = max(self.model.ajump or 0.0, 0.15)
        if self.exhaust_count >= 9:
            self.ended = True
            return self.dialogue.choose("MADEXIT") or self.dialogue.choose("BYE")
        return self.dialogue.choose("EXHAUST") or self.dialogue.choose("QREPLIES")

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
