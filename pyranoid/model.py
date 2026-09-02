"""PARRY's paranoid affect model.

Ported from original/src/opar3 (flares, delusion, decay) and the affect engine
in pmem2/pmem4/pmem5 (RAISE, the mode functions, paranoid-mode activation).

The four affect variables ANGER, FEAR, MISTRUST, HURT range 0..20. Each turn,
detected flares / delusion references / insults set "jumps" (FJUMP, AJUMP, HJUMP)
which RAISE() applies with a saturating update ``x += jump*(20-x)``. The base
values (…0) drift upward permanently, so PARRY grows more sensitised as an
interview goes on. MODIFVAR() decays the variables back toward base each turn.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyranoid import parry_data as D

CEIL = 20.0


@dataclass
class Affect:
    """The four affect variables and their (drifting) base values."""

    anger: float = 0.0
    fear: float = 0.0
    mistrust: float = 0.0
    hurt: float = 0.0
    anger0: float = 0.0
    fear0: float = 0.0
    mistrust0: float = 0.0
    hurt0: float = 0.0

    def snapshot(self) -> dict:
        return {"anger": round(self.anger, 2), "fear": round(self.fear, 2),
                "mistrust": round(self.mistrust, 2), "hurt": round(self.hurt, 2)}


class Model:
    """PARRY's emotional and delusional state machine."""

    def __init__(self, version: str = "STRONG"):
        version = version.upper()
        if version not in D.VERSION_BASELINE:
            version = "STRONG"
        self.version = version
        self.weak = version == "WEAK"

        base = D.VERSION_BASELINE[version]
        self.affect = Affect(
            anger=base, fear=base, mistrust=base, hurt=base,
            anger0=base, fear0=base, mistrust0=base, hurt0=base,
        )

        # per-turn "jumps"; None means no change this turn
        self.fjump: float | None = None
        self.ajump: float | None = None
        self.hjump: float | None = None

        # flare / delusion state
        self.flare: str = "INIT"            # current flare set, INIT = none
        self.weight: float = 0.0            # weight of the current flare word
        self.delflag: bool = False          # delusions under discussion
        self.delend: bool = False           # finished with delusions
        self.topic: str = "INIT"            # current self-topic
        self.live_flares: set[str] = set(D.FLARE_WEIGHTS) - {"INIT", "MAFIASET"}
        self.live_flares = {f for f in D.FLARE_WORDS if f != "MAFIASET"}
        self.dead_flares: set[str] = set()

    # -- flare handling (opar3: CHECKFLARE, FLRECORD, FLMOD) ----------------

    def check_flare(self, words: list[str], among: set[str], mark: bool) -> bool:
        """Find the highest-weight flare word in `words` drawn from `among`.

        Sets self.flare / self.weight when a strong-enough flare is found.
        Mirrors opar3 CHECKFLARE. Returns True if a flare was recorded.
        """
        w2f = D.word_to_flare()
        best_set = "INIT"
        best_wt = D.FLARE_WEIGHTS["INIT"]
        for w in words:
            fset = w2f.get(w)
            if fset and fset in among:
                wt = D.FLARE_WEIGHTS.get(fset, 0)
                if wt > best_wt:
                    best_set, best_wt = fset, wt
        if best_set == "INIT":
            return False
        # if a flare is already active, ignore a very weak new one
        if self.flare != "INIT" and not best_wt > 1:
            return False
        self.flare = best_set
        self.weight = best_wt
        return True

    def _flmod(self, fset: str) -> None:
        """Move a flare from the live list to the dead list."""
        self.live_flares.discard(fset)
        self.dead_flares.add(fset)

    def flare_reference(self, words: list[str]) -> str | None:
        """opar3 FLAREREF: raise fear on a new flare; answer an old one."""
        if self.check_flare(words, self.live_flares, mark=False):
            self._flrecord(self.flare)
        if self.check_flare(words, self.dead_flares, mark=True):
            return self.flare
        return None

    def _flrecord(self, fset: str) -> None:
        self._flmod(fset)
        self.fjump = self.weight / 40.0
        self.topic = fset

    # -- delusion handling (opar3: DELREF, DELSTMT) ------------------------

    def delusion_reference(self, found_strong: bool) -> None:
        """opar3 DELREF: entering / deepening delusional discussion."""
        if self.delflag:
            self.fjump = 0.4 if found_strong else 0.1
        else:
            self.fjump = 0.5
            self._flmod("MAFIASET")
        if not self.delend:
            self.delflag = True
        self.flare = "INIT"
        self.topic = "DELUSIONS"

    # -- affect engine (pmem2 RAISE, opar3 MODIFVAR) -----------------------

    def raise_affect(self) -> None:
        """Apply the pending jumps with saturating updates (pmem2 RAISE)."""
        a = self.affect
        if self.hjump is not None:
            hj = 0.5 * self.hjump if self.weak else self.hjump
            a.hurt += hj * (CEIL - a.hurt)
            a.mistrust += 0.5 * hj * (CEIL - a.mistrust)
            a.mistrust0 += 0.1 * hj * (CEIL - a.mistrust0)
            a.hurt0 = max(a.hurt / 2, a.hurt0)
            a.fear0 = max(a.fear0, a.hurt0 / 2)
            a.fear = max(a.fear, a.fear0)
            a.anger0 = max(a.anger0, a.hurt0 / 2)
            a.anger = max(a.anger, a.anger0)
        if self.fjump is not None:
            fj = self.fjump + a.hurt / 50.0   # fear volatile on high hurt
            if self.weak:
                fj *= 0.3
            a.fear += fj * (CEIL - a.fear)
            a.mistrust += 0.5 * fj * (CEIL - a.mistrust)
            a.mistrust0 += 0.1 * fj * (CEIL - a.mistrust0)
        if self.ajump is not None:
            aj = self.ajump + a.hurt / 50.0   # anger volatile on high hurt
            if self.weak:
                aj *= 0.7
            a.anger += aj * (CEIL - a.anger)
            a.mistrust += 0.5 * aj * (CEIL - a.mistrust)
            a.mistrust0 += 0.1 * aj * (CEIL - a.mistrust0)
        # Defensive clamp. With in-spec jumps (<=~0.6) the saturating update
        # already keeps every variable in [base, 20); this only guards against
        # a pathological out-of-range jump and never alters faithful behaviour.
        a.anger = min(a.anger, CEIL)
        a.fear = min(a.fear, CEIL)
        a.mistrust = min(a.mistrust, CEIL)
        a.hurt = min(a.hurt, CEIL)

    def modify_vars(self) -> None:
        """Per-turn decay toward base values (opar3 MODIFVAR)."""
        a = self.affect
        a.anger = max(a.anger - 1, a.anger0)
        a.hurt = max(a.hurt - 0.5, a.hurt0)
        if self.delflag:
            a.fear = max(a.fear - 0.1, a.fear0 + 5)
        elif self.flare != "INIT":
            a.fear = max(a.fear - 0.2, a.fear0 + 3)
        else:
            a.fear = max(a.fear - 0.3, a.fear0)
        a.mistrust = max(a.mistrust - 0.05, a.mistrust0)
        self.fjump = self.ajump = self.hjump = None

    # -- mode selection (pmem4 ANGERFEARMODE / FEARMODE / ANGERMODE) --------

    def anger_fear_mode(self, topic: str) -> str | None:
        """Pick a diffuse-affect response group, or None to defer.

        Returns the name of a response group ('ANGER', 'HOSTILEREPLIES',
        'EXIT', 'THREATQ', 'AFRAID', ...) or None.
        """
        flare_sets = set(D.FLARE_WORDS) | {"MAFIA"}
        if topic in flare_sets or topic in {
            "BYE", "IYOUME", "STRONGFEELINGS", "FEELINGS", "GAMES",
        }:
            return None
        return self.fearmode() if self.affect.fear >= 14 else self.angermode()

    def angermode(self) -> str:
        return "ANGER" if self.affect.anger > 17.5 else "HOSTILEREPLIES"

    def fearmode(self, is_question: bool = False) -> str:
        a = self.affect
        if a.fear > 18.4:
            return "EXIT"  # caller sets end-of-interview
        if is_question:
            return "THREATQ"
        return "AFRAID"

    # -- paranoid-mode activation (pmem5) ----------------------------------

    def paranoid_intent(self) -> str | None:
        """After RAISE, decide whether delusional or strong-feeling mode fires.

        Returns 'PPARANOIA', 'PSTRONGFEEL', or None.
        """
        a = self.affect
        strong_trip = self.version == "STRONG" and (
            a.hurt >= 7 or (self.hjump is not None and self.hjump >= 0.1)
        )
        mild_trip = self.version == "MILD" and a.hurt >= 8
        if strong_trip or mild_trip:
            return "PPARANOIA"
        if (
            (self.fjump is not None and self.fjump >= 0.01)
            or (self.ajump is not None and self.ajump >= 0.01)
            or a.fear >= 14 or a.anger >= 14
        ):
            return "PSTRONGFEEL"
        return None
