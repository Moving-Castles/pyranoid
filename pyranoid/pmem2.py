"""Affect raising, keyword scan, semantic functions, dates (``pmem2``).

Routine-for-routine port of the second memory file: INITF and the anaphor
synonym table; the FLARESENT / DELNSENT / SILENCER / EXHAUSTER / SWEARER /
ENDROUTINE semantic functions that PDAT units name in their SF property;
RAISE, the affect update; SKEYWD / KEYWD, the keyword fall-back used when
the pattern matcher recognised nothing; Q; CANONA; the date and time
answers; SPECCONCEPT and LASTWORD for sensitive topics.

The calendar arithmetic in DATE is Colby's (no leap years after 1973 --
"previous line should be fixed on Feb 29, 1976"); it is kept as written.
"""

from __future__ import annotations

import datetime as _dt

from pyranoid.lisp import (
    NIL,
    T,
    assoc,
    atom,
    caddr,
    cadr,
    car,
    cddr,
    cdr,
    cons,
    delete,
    is_nil,
    last,
    member,
    memq,
    to_list,
    truthy,
    words,
)

_QWORDS = ["IS", "ARE", "WAS", "WERE", "AM", "DID", "DOES", "DO", "HAVE", "HAS", "HAD",
           "WHO", "WHOM", "WHAT", "WHEN", "WHERE", "HOW", "WHY", "CAN", "COULD",
           "WOULD", "SHOULD", "WILL", "MAY"]

_MONTHS = [(31, "JANUARY"), (28, "FEBRUARY"), (31, "MARCH"), (30, "APRIL"), (31, "MAY"),
           (30, "JUNE"), (31, "JULY"), (31, "AUGUST"), (30, "SEPTEMBER"), (31, "OCTOBER"),
           (30, "NOVEMBER"), (31, "DECEMBER")]
_DAYS = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]


class Pmem2Mixin:
    # -- INITF ------------------------------------------------------------------------

    def initf(self):
        self.EXHAUSTNO = self.SILENCENO = self.SWEARNO = 0
        self.ALLANAPHS = [
            ["WHO"],
            ["THEY", "HE", "SHE", "WE"],
            ["HE"], ["SHE"], ["WE"],
            ["THERE", "WHERE"], ["HERE", "THERE", "WHERE"], ["WHERE"],
            ["THEN", "WHEN"], ["WHEN", "HOW_LONG"], ["HOW_LONG"],
            ["IT"], ["WHAT"], ["YOU_DO"], ["THEY_DO"], ["HOW_MUCH"], ["HOW_KNOW"],
            ["GO_ON"], ["ELAB"], ["WHY"], ["HOW"], ["YES"], ["NO"],
        ]

    # -- FLARESENT / DELNSENT: SFs of flare and delusion units ----------------------

    def flaresent(self):
        self.flareref(self.INPUTQUES)     # deactivate new flare words, compute FJUMP
        return NIL

    def delnsent(self):
        a = self.delcheck(self.INPUTQUES)
        return self.delref(a)

    # -- RAISE ------------------------------------------------------------------------

    def raise_(self):
        if truthy(self.HJUMP):
            if truthy(self.WEAK):
                self.HJUMP = 0.5 * self.HJUMP
            self.HURT = self.HURT + self.HJUMP * (20 - self.HURT)
            self.MISTRUST = self.MISTRUST + (0.5 * self.HJUMP) * (20 - self.MISTRUST)
            self.MISTRUST0 = self.MISTRUST0 + 0.1 * self.HJUMP * (20 - self.MISTRUST0)
            self.HURT0 = self.lmax(self.HURT / 2, self.HURT0)
            # a higher floor on fear and anger due to hurt
            self.FEAR0 = self.lmax(self.FEAR0, self.HURT0 / 2)
            self.FEAR = self.lmax(self.FEAR, self.FEAR0)
            self.ANGER0 = self.lmax(self.ANGER0, self.HURT0 / 2)
            self.ANGER = self.lmax(self.ANGER, self.ANGER0)
        if truthy(self.FJUMP):
            self.FJUMP = self.FJUMP + self.HURT / 50        # fear volatile on high hurt
            if truthy(self.WEAK):
                self.FJUMP = 0.3 * self.FJUMP
            self.FEAR = self.FEAR + self.FJUMP * (20 - self.FEAR)
            self.MISTRUST = self.MISTRUST + (0.5 * self.FJUMP) * (20 - self.MISTRUST)
            self.MISTRUST0 = self.MISTRUST0 + 0.1 * self.FJUMP * (20 - self.MISTRUST0)
        if truthy(self.AJUMP):
            self.AJUMP = self.AJUMP + self.HURT / 50        # anger volatile on high hurt
            if truthy(self.WEAK):
                self.AJUMP = 0.7 * self.AJUMP
            self.ANGER = self.ANGER + self.AJUMP * (20 - self.ANGER)
            self.MISTRUST = self.MISTRUST + (0.5 * self.AJUMP) * (20 - self.MISTRUST)
            self.MISTRUST0 = self.MISTRUST0 + 0.1 * self.AJUMP * (20 - self.MISTRUST0)

    @staticmethod
    def numed(n) -> str:
        """NUMED: 0.00 <= N <= 99.99 as "12.34"."""
        return f"{int(n * 100 + 0.5) / 100:5.2f}"

    # -- SKEYWD / KEYWD: only when the pattern matcher recognised nothing -----------

    def skeywd(self, type_, sent):
        found = NIL
        if truthy(self.DELFLAG):
            r = self.delcheck(sent)
            if truthy(r):
                r = self.delref(r)
                found = r if truthy(r) else self.delstmt()
        if is_nil(found) and self.FLARE != "INIT":
            r = self.flareref(sent)
            if truthy(r):
                found = self.flstmt(r)
        if is_nil(found):
            found = self.keywd(sent, self.SETLIST)
        if is_nil(found):
            found = self.speconcept(NIL)
        return found

    def keywd(self, inp, setlist):
        """KEYWD: a key word of a special topic answers only if the topic is
        the same as the previous topic."""
        result = NIL
        set_ = NIL
        for set_ in to_list(self.getprop("SETLIST", "SETS")):
            for word in to_list(self.getprop(set_, "WORDS")):
                if truthy(assoc(word, inp)):
                    result = set_
                    break
            if truthy(result):
                break
        if is_nil(result):
            return NIL
        set_ = result
        result = self.getprop(result, "STORY")
        if is_nil(result):
            return NIL
        a = self.OLDTOPIC if self.STOPIC == "ANAPH" else self.STOPIC
        if self.synnym(a) == self.synnym(set_):
            return car(result)
        return NIL

    # -- SILENCER / EXHAUSTER / SWEARER / ENDROUTINE ---------------------------------

    def silencer(self):
        self.SILENCENO = self.SILENCENO + 1
        if self.SILENCENO == 11:
            self.ENDE = T
        self.AJUMP = 0.1
        return NIL

    def exhauster(self):
        self.EXHAUSTNO = self.EXHAUSTNO + 1
        self.AJUMP = 0.15
        if self.EXHAUSTNO == 9:
            self.ENDE = T
            return self.choose("MADEXIT")
        return NIL

    def swearer(self):
        self.SWEARNO = self.SWEARNO + 1
        self.AJUMP = 0.3
        if self.SWEARNO == 5:
            self.ENDE = T
            return self.choose("MADEXIT")
        return NIL

    def endroutine(self):
        self.ENDE = T
        if self.FEAR <= 18.4 and (truthy(self.DELFLAG) or self.FLARE == "INIT"):
            self.AJUMP = 0.1
            return self.choose("BYEOFF")
        return self.choose("BYE")

    # -- Q, CANONA, MEMFIND ------------------------------------------------------------

    @staticmethod
    def q(l):
        """Q: 'Q if the input is a question, else 'D."""
        if is_nil(l):
            return "D"
        if car(last(l)) == "QM":
            return "Q"
        if truthy(member(car(l), _QWORDS)):
            return "Q"
        return "D"

    def canona(self, l):
        """CANONA: run an output sentence back through CANONIZE (for ASCAN)."""
        a = self.INPUTQUES
        c = self.DO_SPELL
        self.DO_SPELL = NIL
        self.canonize(cdr(l) if truthy(l) and not atom(car(l)) else l)
        b = self.INPUTQUES
        self.DO_SPELL = c
        self.INPUTQUES = a
        return b

    @staticmethod
    def memfind(struc):
        return struc

    # -- INITPARAMS: the version and non-verbal settings ------------------------------

    def initparams(self, version="STRONG", suppress=False):
        self.SUPPRESS = T if suppress else NIL
        version = version.upper()
        if version.startswith("W"):
            self.WEAK = T
            self.VERSION = "WEAK"
        else:
            if version.startswith("S"):
                self.VERSION = "STRONG"
                base = 5
            else:
                self.VERSION = "MILD"
                base = 0
            self.ANGER = self.ANGER0 = self.FEAR = self.FEAR0 = base
            self.MISTRUST = self.MISTRUST0 = self.HURT = self.HURT0 = base
        self.SAVE_FILE = T

    # -- DATE / GET_DATE / GET_TIME ------------------------------------------------------

    def dateuu(self) -> int:
        """DATE UUO: ((year-1964)*12 + month-1)*31 + day-1 for today."""
        d = self.clock().date()
        return ((d.year - 1964) * 12 + (d.month - 1)) * 31 + (d.day - 1)

    def timeuu(self) -> int:
        """TIMER UUO: jiffies (1/60 s) since midnight."""
        t = self.clock()
        return (t.hour * 3600 + t.minute * 60 + t.second) * 60

    def clock(self) -> _dt.datetime:
        return self._clock() if self._clock else _dt.datetime.now()  # noqa: DTZ005

    def date(self, n):
        a = self.dateuu() + n                  # -1 yesterday, 0 today, +1 tomorrow
        a, date_ = divmod(a, 31)
        date_ += 1
        a, mo = divmod(a, 12)
        mo += 1
        yr = a + 1964
        a = 0
        for i in range(1, mo):
            a += _MONTHS[i - 1][0]
        for _ in range(1973, yr + 1):
            a += 365
        a += date_ - 1
        a = a % 7 + 1                           # oriented for 1973 and beyond
        day = _DAYS[a - 1]
        return [yr, _MONTHS[mo - 1][1], date_, day]

    def getdocname(self):
        """GETDOCNAME: the doctor's name from "my name is X" / "I am Dr X"."""
        a = delete("PD", self.SSENT)
        a = delete("COMMA", a)
        c = NIL
        doc = NIL
        b = a
        while True:
            if car(b) == "MY" and cadr(b) == "NAME" and caddr(b) == "IS":
                c = cdr(cddr(b))
            b = cdr(b)
            if truthy(c) or is_nil(b):
                break
        b = a
        if is_nil(c):
            while True:
                if car(b) == "I" and cadr(b) == "AM" and caddr(b) in ("DR", "DOCTOR"):
                    c = cdr(cddr(b))
                    doc = T
                b = cdr(b)
                if truthy(c) or is_nil(b):
                    break
        b = a
        if is_nil(c):
            while True:
                if car(b) in ("I'M", "IM") and cadr(b) in ("DR", "DOCTOR"):
                    c = cddr(b)
                    doc = T
                b = cdr(b)
                if truthy(c) or is_nil(b):
                    break
        if car(c) in ("DR", "DOCTOR"):
            doc = T
            c = cdr(c)
        if is_nil(c):
            return NIL
        name = [car(c)]
        if truthy(cdr(c)):
            test = cadr(c)
            if is_nil(self.canona([test])):
                name = [car(c), cadr(c)]
        if truthy(doc):
            name = cons("DOCTOR", name)
        return name

    def get_date(self, a, n):
        b = self.date(n)
        if is_nil(b):
            return ["I", "DON'T", "PLAY", "GAMES"]
        yr, mo, date_, day = b
        if a in ("YEAR", "MONTH"):
            return ["THE", "YEAR", "IS", f"{yr};", "THE", "MONTH", "IS", mo]
        if a == "DATE":
            return ["TODAY", "IS", mo, f"{date_},", "I", "THINK"]
        if a == "DAY":
            return ["IT'S", day]
        return NIL

    def get_date_arb2(self, n):
        a = assoc("DAY", self.INPUTQUES)
        if is_nil(a):
            a = assoc("DATE", self.INPUTQUES)
        if truthy(a) and truthy(memq(cdr(a), ["YEAR", "MONTH", "DAY", "DATE"])):
            return self.get_date(cdr(a), n)
        if is_nil(a):
            a = assoc("WHEN", self.INPUTQUES)
        if truthy(a) and (cdr(a) == "TIME" or car(a) == "WHEN"):
            return self.get_time()
        return NIL

    def get_date_arb(self):
        return self.get_date_arb2(0)

    def get_date_yes(self):
        return self.get_date_arb2(-1)

    def get_date_tom(self):
        return self.get_date_arb2(1)

    def get_time(self):
        hour, minute = self.timeuuh()
        ahour = hour + minute // 30
        if ahour >= 13:
            ahour = ahour - 12
        if ahour == 0:
            ahour = 12
        return ["IT'S", "ABOUT", f"{ahour} O", "CLOCK"]

    def timeuuh(self):
        """TIMEUUH: (HOUR MINUTE) -- jiffies/3600 = minutes, then /60."""
        a = self.timeuu() // 3600
        return [a // 60, a % 60]

    # -- SPECCONCEPT / LASTWORD: sensitive topics -----------------------------------------

    def speconcept(self, l):
        """SPECCONCEPT: an IYOUME input on a sensitive topic the matcher missed."""
        inp = self.INPUTQUES
        con = NIL
        for word in to_list(inp):
            if truthy(member(self.getprop(car(word), "SET"), self.SENSITIVELIST)):
                con = car(word)
                break
        if is_nil(con):
            return NIL
        you = T if truthy(assoc("YOU", inp)) else NIL
        neg = self.NOT_FLAG
        adj = NIL
        if truthy(assoc("GOOD", inp)):
            adj = "GOOD"
        elif truthy(assoc("BAD", inp)) or truthy(assoc("ODD", inp)):
            adj = "BAD"
        if truthy(you) and truthy(adj):
            if (adj == "GOOD" and is_nil(neg)) or (truthy(neg) and adj == "BAD"):
                found = self.choose("POSADJ")
            else:
                found = self.choose("NEGADJ")
        elif truthy(you) and (truthy(self.getprop(con, "SPECIAL")) or truthy(adj)):
            found = self.choose("SPECCONCEPT")
        else:
            found = self.choose("SENSITIVELIST")
        return found

    def lastword(self, l):
        """LASTWORD: the English word(s) WDFLAG says to append to the output."""
        a = NIL
        w = l
        if w == "SENSITIVELIST":
            w = T
            for i in to_list(self.getprop("SENSITIVELIST", "WORDS")):
                a = assoc(i, self.INPUTQUES)
                if truthy(a):
                    a = self.getprop(car(a), "SET")
                    break
        if w == "COMPLEMENT":
            w = T
            a = assoc("GOOD", self.INPUTQUES)
            if truthy(a):
                a = cdr(a)
        if w == "SPEC_CONCEPT":
            w = T
            a = assoc("LOOKS", self.INPUTQUES)
            a = car(self.getprop(car(a), "WORDS")) if truthy(a) else "LOOKS"
        if truthy(a):
            return [a]
        if w is T or is_nil(w):
            return ["PROBLEMS"]
        if atom(w):
            return [w]
        return w

    @staticmethod
    def stringate(l) -> str:
        """STRINGATE: the printed sentence without its outer parentheses."""
        return words(l)
