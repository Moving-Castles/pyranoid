"""PARRY's belief/inference engine (the "doctor model").

Ported from pmem4 (READBEL/READINF/POSIT/ASSERT2/ADDTO/PROVE/PROVE2/EVALUATE/
BL/STATED/INFERENCE), pmem5 (MEASURE, AFFECT, INFEMOTE, INTENTION, DOINTENT and
the intent routines), and the bel/inf data.

Each turn the matched input unit's TH2 hooks assert beliefs about the doctor
(DMAFIA, DDHARM, DHOSTILE, DINSULTS, DBABNORMAL, …) or about the self (CRAZY,
DUMB, LOSER, LYING). Asserting a belief fires its EMOTE rules, which arm the
HURT/FEAR/ANGER jumps that RAISE then applies. IF-theorems forward-chain to more
beliefs and to intention scores; the highest-priority intention above threshold
drives the reply.

Beliefs carry two values: NTRUTH (a graded accumulator) and TRUTH (asserted
flag). BL(b) = NTRUTH>=5 for intentions, else the TRUTH flag.
"""

from __future__ import annotations

from typing import ClassVar

from pyranoid.beliefs import BeliefBase


def _is_unit(tok: str) -> bool:
    return isinstance(tok, str) and tok[:1] in "HP" and tok[1:].isdigit()


class Inference:
    def __init__(self, bb: BeliefBase, model):
        self.bb = bb
        self.model = model
        self.oppos = bb.oppos()
        self.intent_order = bb.intentions()          # low -> high priority

        # reverse indices from inf ----------------------------------------
        self.unit_th2: dict[str, list] = {}          # unit  -> [consequent]
        self.belief_parents: dict[str, list] = {}    # belief-> [parent belief]
        for consequent, items in bb.th2_raw:
            for item in items:
                if _is_unit(item):
                    self.unit_th2.setdefault(item, []).append(consequent)
                else:  # item is a belief -> grouping propagation in ADDTO
                    parent = consequent[0] if isinstance(consequent, tuple) else consequent
                    self.belief_parents.setdefault(item, []).append(parent)
        self.emote: dict[str, list] = {}             # belief -> [(jumpvar, mag)]
        for e in bb.emotes:
            for b in e.beliefs:
                self.emote.setdefault(b, []).append((e.jump, e.value))
        # IF theorems: tag -> (consequent, antecedents)
        self.theorems = {r.tag: (r.consequent, r.antecedents) for r in bb.rules}
        # antecedent back-indices: belief -> theorems (forward chaining, GET(B,'TH))
        # and unit -> theorems (unit-keyed, GET(REACTTO,'TH))
        self.belief_theorems: dict[str, list] = {}
        self.unit_theorems: dict[str, list] = {}
        for tag, (_cons, antes) in self.theorems.items():
            for a in antes:
                name = a if isinstance(a, str) else (a[1] if len(a) > 1 else None)
                if not isinstance(name, str):
                    continue
                if _is_unit(name):
                    self.unit_theorems.setdefault(name, []).append(tag)
                else:
                    self.belief_theorems.setdefault(name, []).append(tag)

        self.reset()

    # theorems tried on every turn (INFERENCE PROVEL seed, pmem4)
    ALWAYS_TRY: ClassVar[list[str]] = [
        "IF730", "IF740", "IF750", "IF760", "IF770",
        "IF350", "IF380", "IF566", "IF884", "IF225",
    ]

    def reset(self) -> None:
        self.ntruth: dict[str, float] = {n: b.value for n, b in self.bb.beliefs.items()}
        self.truth: set[str] = set()
        self.parbel: list[str] = []      # HJUMP shame sources, for PARANOIA()
        self.reactto: str | None = None
        self.provel: list[str] = []      # theorem work queue (PROVEL)

    # -- belief tests -------------------------------------------------------

    def _cls(self, b: str) -> str:
        bd = self.bb.beliefs.get(b)
        return bd.cls if bd else ""

    def bl(self, b: str) -> bool:
        if self._cls(b) == "INN":
            return self.ntruth.get(b, 0) >= 5
        return b in self.truth

    def score(self, intent: str) -> float:
        return self.ntruth.get(intent, 0.0)

    # -- emotion jumps (INFEMOTE) ------------------------------------------

    def _infemote(self, belief: str, jumps: list, asserted: bool) -> None:
        m = self.model
        for jvar, mag in jumps:
            c = mag
            if jvar == "HJUMP":
                self.parbel.append(belief)
                if m.weak:
                    c /= 2
            if not asserted:          # came from ADDTO (graded) -> half strength
                c /= 2
            attr = jvar.lower()       # hjump / fjump / ajump
            cur = getattr(m, attr) or 0.0
            setattr(m, attr, max(cur, c))

    # -- assertion / accumulation (ASSERT2 / ADDTO / POSIT) ----------------

    def assert2(self, b: str) -> None:
        if b in self.emote:
            self._infemote(b, self.emote[b], asserted=True)
        opp = self.oppos.get(b)
        if b in self.truth:
            return
        if opp and opp in self.truth:
            return                    # opposite already asserted -> contradiction
        self.truth.add(b)
        if opp:
            self.truth.discard(opp)   # unassert the opposite
        # forward chain: re-queue theorems in which b is an antecedent
        for tag in self.belief_theorems.get(b, ()):
            self.provel.append(tag)

    def addto(self, b: str, n: float) -> None:
        if b in self.emote:
            self._infemote(b, self.emote[b], asserted=False)
        for parent in self.belief_parents.get(b, ()):  # grouping, half strength
            self.addto(parent, n / 2)
        opp = self.oppos.get(b)
        if b in self.truth or (opp and opp in self.truth):
            return
        val = n + self.ntruth.get(b, 0.0)
        if self._cls(b) == "INN":     # intentions clamp to [0, 9]
            val = min(9, max(0, val))
        self.ntruth[b] = val
        if val >= 10:
            self.assert2(b)

    def posit(self, consequent) -> None:
        # consequent: a belief atom (ASSERT2), or (belief, n) / [belief, n] (ADDTO n)
        if isinstance(consequent, (tuple, list)):
            name = consequent[0]
            n = float(consequent[1]) if len(consequent) > 1 else 2.0
            self.addto(name, n)
        else:
            self.assert2(consequent)

    def add_to_intent(self, intent: str, n: float) -> None:
        self.addto(intent, n)

    # -- antecedent evaluation (EVALUATE / MEASURE) ------------------------

    def _val(self, x, ctx: dict):
        if isinstance(x, str):
            if x.lstrip("-").isdigit():
                return int(x)
            up = x.upper()
            if up in ctx:
                return ctx[up]
            return x
        return x

    def _evaluate(self, ante, ctx: dict) -> bool:
        if isinstance(ante, str):
            if _is_unit(ante):
                return ante == self.reactto            # STATED
            return self.bl(ante)                       # belief truth
        if not isinstance(ante, list) or not ante:
            return False
        op = ante[0]
        if op == "NOT":
            return not self.bl(ante[1]) if len(ante) > 1 else True
        if op == "MEASURE" and len(ante) >= 3:
            a, b = self._val(ante[1], ctx), self._val(ante[2], ctx)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a > b
            return a == b
        if op == "GREATERP" and len(ante) >= 3:
            a, b = self._val(ante[1], ctx), self._val(ante[2], ctx)
            return isinstance(a, (int, float)) and isinstance(b, (int, float)) and a > b
        if op == "EQ" and len(ante) >= 3:
            return self._val(ante[1], ctx) == self._val(ante[2], ctx)
        if op == "NULL" and len(ante) >= 2:
            return not self.bl(ante[1])
        return False                                   # unsupported form: inert

    def _consequent_belief(self, cons) -> str:
        return cons[0] if isinstance(cons, (tuple, list)) else cons

    # -- the inference pass (INFERENCE / PROVE) ----------------------------

    def infer(self, reactto: str | None, ctx: dict) -> None:
        """Assert beliefs from the matched unit, then forward-chain (PROVE).

        Each theorem is tried at most once per turn (PROVE consumes PROVEL) and is
        re-queued only when a belief it depends on is asserted. This matches the
        original so intent scores accumulate by a single firing, not runaway.
        """
        self.reactto = reactto
        # seed the queue with the always-try list + the theorems keyed to the
        # matched unit; belief-gated theorems enter only via forward chaining
        # (ASSERT2 re-queues them) — this matches PROVE and prevents double firing.
        self.provel = [t for t in self.ALWAYS_TRY if t in self.theorems]
        if ctx.get("STOPIC") == "MAFIA" and "IF888" in self.theorems:
            self.provel.append("IF888")
        if reactto:
            self.provel.extend(self.unit_theorems.get(reactto, ()))
            for consequent in self.unit_th2.get(reactto, ()):
                self.posit(consequent)
        steps = 0
        while self.provel and steps < 4000:
            steps += 1
            tag = self.provel.pop(0)
            cons, antes = self.theorems[tag]
            cb = self._consequent_belief(cons)
            if self.bl(cb):
                continue
            if all(self._evaluate(a, ctx) for a in antes):
                self.posit(cons)

    # -- intent selection (INTENTION) --------------------------------------

    def winning_intent(self, forced: str | None = None) -> str | None:
        """Highest-priority intention with score >= 5.

        A forced intent (AFFECT's PPARANOIA/PSTRONGFEEL) wins unless the score
        winner is PEXIT/PEXIT2, which always override.
        """
        winner = None
        for i in self.intent_order:           # low -> high priority; last wins
            if self.score(i) >= 5:
                winner = i
        if forced and winner not in ("PEXIT", "PEXIT2"):
            return forced
        return winner or forced
