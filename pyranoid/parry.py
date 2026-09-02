"""PARRY: the whole program as one image, and the interview loop.

``Parry`` composes the routine-for-routine ports of the original source
files -- ``front.lap`` (FrontMixin), ``opar3`` (OparMixin), ``pmem``
(PmemMixin), ``pmem2`` (Pmem2Mixin), ``pmem4`` (Pmem4Mixin) and ``pmem5``
(Pmem5Mixin) -- onto a single property-list image, the way the original ran
as one LISP core image.  Every SPECIAL variable of the original is an
attribute with the original's name (``FEAR``, ``AJUMP``, ``DELFLAG``,
``INPUTQUES`` ...; the ``?!`` sigil is dropped: ``!OUTPUT`` is ``OUTPUT``).

Initialisation follows the build scripts (``dor``): PMINITIALIZE loads the
front-end tables; INITFB runs INITF and INITB (RDATA, PDATB, SETUPSTL,
CHANGE); BINIT reads BEL and INF; INF sets the version parameters; the
memory file PDATZ is read.  ``respond(line)`` is PARRY2 for each sentence
on the line, as the original's READY: loop.
"""

from __future__ import annotations

import random as _random
from dataclasses import dataclass, field
from pathlib import Path

from pyranoid.front import FrontMixin
from pyranoid.lisp import NIL, Lisp, LispError, Plist, is_nil, truthy
from pyranoid.opar import OparMixin
from pyranoid.pmem import PmemMixin
from pyranoid.pmem2 import Pmem2Mixin
from pyranoid.pmem4 import Pmem4Mixin
from pyranoid.pmem5 import Pmem5Mixin

DATA_DIR = Path(__file__).resolve().parent / "data"

# the ?! globals: attribute name -> LISP symbol
_BANG = {
    "ANAPHLIST": "!ANAPHLIST", "ANAPHLISTOLD": "!ANAPHLISTOLD", "ANAPHLISTNEW": "!ANAPHLISTNEW",
    "CLIST": "!CLIST", "CLAST": "!CLAST", "ALLANAPHS": "!ALLANAPHS", "LASTIN": "!LASTIN",
    "LASTOUT": "!LASTOUT", "LAST_ANDTHEN": "!LAST_ANDTHEN", "OUTPUT": "!OUTPUT",
    "LAST_OUTPUT": "!LAST_OUTPUT", "EXHAUST": "!EXHAUST", "ERROR_LIST": "!ERROR",
}
_SYMBOL_TO_ATTR = {v: k for k, v in _BANG.items()}

# every SPECIAL variable, with its value at load time
_SPECIALS: dict = {
    # pmem / pmem2 / pmem4 / pmem5
    "ANAPHLIST": NIL, "ANAPHLISTOLD": NIL, "ANAPHLISTNEW": NIL, "CLIST": NIL, "CLAST": NIL,
    "ALLANAPHS": NIL, "LASTIN": NIL, "LASTOUT": NIL, "LAST_ANDTHEN": NIL, "OUTPUT": NIL,
    "LAST_OUTPUT": NIL, "EXHAUST": NIL, "ERROR_LIST": NIL, "WDFLAG": NIL, "REACTTO": NIL,
    "ERRNAME": NIL, "STYPE": NIL, "STOPIC": NIL, "TRACE_MEM": NIL, "ENDE": NIL,
    "INPUTQUES": NIL, "SSENT": NIL, "DO_SPELL": NIL, "NEXT_CHAR": " ", "MISSPELL": NIL,
    "INPUTSSENT": NIL, "DOCNAME": NIL, "DOC_NAME_FLAG": NIL, "EXHAUSTNO": 0, "SILENCENO": 0,
    "SWEARNO": 0, "PMINPUT": NIL, "PM2INPUT": NIL, "BUG": 0, "REACTINPUT": NIL,
    "INPUTNO": 0, "REPEATNO": 0, "SPECFNNO": 0, "MISCNO": 0, "NEWTOPICNO": 0,
    "OLDTOPIC": NIL, "OLDTOPICS": NIL, "HLIST": NIL,
    "NEWPROVEN": NIL, "INTENT": NIL, "OLDINTENT": NIL, "BADINPUT": NIL, "DELNO": 0,
    "PREV_OUTPUT": NIL, "PREV_SSENT": NIL, "PROVEL": NIL, "PROVEN": NIL, "INTLIST": NIL,
    "PRINTALL": NIL, "OLDGIBB": 0, "OLDMISS": 0, "LOWMAN": NIL, "TRACEVFLAG": NIL,
    "ACTION": NIL, "ONEDIA": NIL, "SUMEX": NIL, "EXPERIMENT": NIL, "STRUC": NIL,
    "PARBEL": NIL, "PARA": NIL, "SPECFNRA": 0, "TYPE": NIL, "SAVE_FILE": NIL, "TRACEV": NIL,
    "SUPPRESS": NIL, "VERSION": NIL,
    # opar3
    "POINTERS": NIL, "DELFLAG": NIL, "FLARE": "INIT", "FLARELIST": NIL, "TOPIC": NIL,
    "DELNLIST": NIL, "DELVLIST": NIL, "DELALIST": NIL, "LIVEFLARES": NIL, "DEADFLARES": NIL,
    "DELEND": NIL, "SENSITIVELIST": NIL, "WEIGHT": NIL, "WEAK": NIL, "CHOSEN": NIL,
    "ANGER": 0, "FEAR": 0, "MISTRUST": 0, "HURT": 0, "ANGER0": 0, "FEAR0": 0, "MISTRUST0": 0,
    "HURT0": 0, "AJUMP": NIL, "FJUMP": NIL, "HJUMP": NIL, "SETLIST": NIL,
    # win
    "WINDOWS": NIL,
    # front.lap
    "USE_CHUCK": NIL, "USE_BILL": NIL, "LEARNING": NIL, "STOP_ON": NIL, "RIGHT": NIL,
    "PATTERN": NIL, "SP_MATCH": NIL, "CP_MATCH": NIL, "NOT_FLAG": NIL, "FAMILY_FLAG": NIL,
    "ANY": NIL, "DID_SPELL": NIL, "GIBBERISH": 0, "MISSPELLED": 0,
}


@dataclass
class Turn:
    """What the original wrote to the DIA file for one I/O pair."""

    user: str
    reply: str
    sentences: list = field(default_factory=list)   # the SSENTs on the line
    unit: object = None                              # PMINPUT (pattern-matcher result)
    bond: object = None                              # its BONDVALUE
    trace: object = None                             # TRACE_MEM
    new_beliefs: object = None                       # NEWPROVEN
    intent: object = None                            # INTENT
    output_unit: object = None                       # !LAST_OUTPUT
    affect: dict = field(default_factory=dict)
    log: list = field(default_factory=list)          # the trace windows


class Parry(FrontMixin, OparMixin, PmemMixin, Pmem2Mixin, Pmem4Mixin, Pmem5Mixin):
    """One PARRY core image: load the data, then ``respond`` to input lines."""

    def __init__(self, data_dir=None, version="STRONG", seed=None, suppress=False,
                 trace=False, clock=None, strict=False):
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self.plist = Plist()
        self.lisp = Lisp(self, self.plist)
        self._rng = _random.Random(seed)
        self._clock = clock
        self.strict = strict
        self.low_memory = False
        self.run_ms = 0
        self.trace_log: list = []
        self.learned: list = []
        self.turns: list[Turn] = []
        self.OUTPUT_TEXT = ""
        self.DIAGNOSTICS: list = []
        for name, value in _SPECIALS.items():
            setattr(self, name, value)
        # the build order of the core image (dor): FRONT, then INITFB, BINIT, INF
        self.pminitialize(self.data_dir)              # PMIN
        self.initf()                                  # INITFB
        self.initb(self.data_dir)
        self.binit(self.data_dir)                     # BINIT
        self.initparams(version, suppress)            # INF -> INITPARAMS
        self.load_pdat(self.data_dir / "pdatz.txt")   # DSKLOC('PDATZ), read on demand originally
        self.TRACEV = "ALL" if trace else NIL
        self.ended = False

    # -- the LISP host interface --------------------------------------------------------

    def lisp_get(self, name):
        attr = _SYMBOL_TO_ATTR.get(name, name)
        try:
            return getattr(self, attr)
        except AttributeError:
            raise LispError(f"unbound variable {name}") from None

    def lisp_set(self, name, value):
        setattr(self, _SYMBOL_TO_ATTR.get(name, name), value)

    def lisp_fn(self, name):
        if not isinstance(name, str):
            return None
        pyname = {"ASSERT": "assert_belief", "RAISE": "raise_"}.get(name, name.lower())
        fn = getattr(self, pyname, None)
        return fn if callable(fn) else None

    def getprop(self, atom_, prop):
        return self.plist.get(atom_, prop)

    def putprop(self, atom_, value, prop):
        return self.plist.put(atom_, value, prop)

    def random(self, n: int) -> int:
        """RANDOM(N): 1..N (the original divided the run time by N)."""
        return self._rng.randint(1, max(int(n), 1))

    def errset(self, thunk):
        """ERRSET: (value) on success, NIL on a LISP error (logged)."""
        try:
            return [thunk()]
        except LispError as e:
            if self.strict:
                raise
            self.ERROR_LIST = [["LISP", str(e), self.BUG]] + list(self.ERROR_LIST or [])
            return NIL
        except (TypeError, AttributeError, IndexError, KeyError, ValueError, ZeroDivisionError) as e:
            if self.strict:
                raise
            self.ERROR_LIST = [["LISP", repr(e), self.BUG]] + list(self.ERROR_LIST or [])
            return NIL

    # -- the interview -------------------------------------------------------------------

    def greeting(self) -> str:
        """The interviewer speaks first; PARRY's opening line is a HELLO reply."""
        unit = self.choose("HELLO")
        self.OUTPUT = NIL
        self.WDFLAG = NIL
        self.ANAPHLISTNEW = NIL
        words = self.express(unit, "RESP")
        self.ANAPHLISTNEW = NIL
        return self.stringate(words) if truthy(words) else "HELLO"

    def respond(self, line: str) -> str:
        """PARRY2 for each sentence on the line; the reply to the last one.

        The original required every input to end with a period or question
        mark; a line without one is given a period.
        """
        text = line.strip()
        if not text or text[-1] not in "!%).?]":
            text = text + " ."
        self.set_input(text + "\n")
        self.NEXT_CHAR = " "
        self.trace_log = []
        self.OUTPUT_TEXT = ""
        sentences: list = []
        while True:
            try:
                self.parry2()
            except LispError:
                if self.strict:
                    raise
                self.OUTPUT_TEXT = "WHAT DO YOU MEAN BY THAT"
            sentences.append(list(self.SSENT or []))
            if not self.not_last_input():
                break
        reply = self.OUTPUT_TEXT
        if truthy(self.ENDE):
            self.ended = True
        turn = Turn(user=line, reply=reply, sentences=sentences,
                    unit=self.PMINPUT, bond=self.getprop(self.REACTINPUT, "BONDVALUE"),
                    trace=self.TRACE_MEM, new_beliefs=self.NEWPROVEN, intent=self.INTENT,
                    output_unit=self.LAST_OUTPUT, affect=self.affect_snapshot(),
                    log=list(self.trace_log))
        self.turns.append(turn)
        return reply

    def affect_snapshot(self) -> dict:
        return {"fear": round(self.FEAR, 2), "anger": round(self.ANGER, 2),
                "mistrust": round(self.MISTRUST, 2), "hurt": round(self.HURT, 2)}

    # -- introspection helpers ------------------------------------------------------------

    def unit_sentences(self, unit):
        """The remaining NORMAL sentences of a ^H unit's response set."""
        b = self.getprop(unit, "RESP")
        if is_nil(b):
            return []
        sents = self.getprop(b, "NORMAL")
        return [s for s in (sents or [])]

    def beliefs_held(self) -> list:
        return sorted(a for a in self.plist.atoms_with("TRUTH") if truthy(self.getprop(a, "TRUTH")))

    def intent_scores(self) -> dict:
        return {i: self.get0(i, "NTRUTH") for i in (self.INTLIST or [])}
