"""Input checking, semantic functions, affect and intentions (``pmem5``).

Routine-for-routine port of the fifth memory file: CHECKINPUT (tiredness,
the FX hook, swearing, bad associations, gibberish, misspelling, and the
"playing games" repetition check); the belief-driven semantic functions
APOLOGY / HELPER / KNOWER / LEADIN / ALOOF / ALOOF2 / NAMECHECK / OPINION /
SELFFEELING / INTERVIEW; AFFECT (raise the emotions, decide whether the
paranoid or strong-feeling mode is forced); INFEMOTE (EMOTE rules -> jumps);
INTENTION / DOINTENT and the intention routines PINTERACT ... PEXIT2; LULL,
PPARANOIA, STRONGFEEL, PARANOIA.

``ANDDO(L, M)`` in the source evaluates both and returns L; it is written
out as sequential statements here.
"""

from __future__ import annotations

from typing import ClassVar

from pyranoid.lisp import (
    NIL,
    LispError,
    T,
    append,
    assoc,
    cadr,
    car,
    cdr,
    cons,
    equal,
    is_nil,
    length,
    member,
    memq,
    numberp,
    to_list,
    truthy,
)

_PARANOIA_CLASS = [["INSULT", "PANGER"], ["CRAZY", "AVOIDANCE"], ["THREAT", "PANIC"],
                   ["ATTACK", "LIE"], ["FEELINGS", "LIE"], ["WEAKINSULT", "PPERS"],
                   ["COMPLEMENT", "PDISTANCE"], ["DISBELIEF", "PBELIEVEREPLIES"],
                   ["APOLOGY", "PACCUSE"]]
_PARANOIA_SF = [["HELPER", "PCAUTION"], ["ALOOF", "PALOOF"], ["ALOOF2", "OPINION"]]
_STRONGFEEL_CLASS = [["INSULT", "ANGER"], ["WEAKINSULT", "PERS"], ["COMPLEMENT", "DISTANCE"],
                     ["SENSATTITUDE", "SENSREPLIES"], ["CRAZY", "HOSTILEREPLIES"],
                     ["THREAT", "PANIC"], ["DISBELIEF", "BELIEVEREPLIES"],
                     ["APOLOGY", "ACCUSE"], ["LYING", "BELIEVEREPLIES"]]
_PARANOIA_PROJECT = [["LYING", "*DHONEST"], ["LOSER", "*DSOCIABLE"],
                     ["CRAZY", "DABNORMAL"], ["DUMB", "*DCHELP"]]


class Pmem5Mixin:
    # -- EXPERIMENT -------------------------------------------------------------------

    def experiment(self):
        """EXPERIMENT: raising and lowering shame at inputs 7 and 17."""
        if is_nil(self.EXPERIMENT) or self.EXPERIMENT != "SEVEN":
            return NIL
        if self.INPUTNO == 7:
            self.HURT = self.HURT + 5
        if self.INPUTNO == 17:
            self.HURT = self.HURT - 5
        return NIL

    def error(self, mess, l):
        """ERROR: record the error (the original wrote a Pnnn.ERR file)."""
        self.ERROR_LIST = cons([mess, l, self.PM2INPUT, self.PMINPUT, self.BUG], self.ERROR_LIST)
        return NIL

    @staticmethod
    def measure(l, m):
        """MEASURE: GREATERP for numbers, else EQ."""
        if numberp(l) and numberp(m):
            return T if l > m else NIL
        return T if equal(l, m) else NIL

    @staticmethod
    def anddo(l, m):
        return l

    # -- CHECKINPUT ---------------------------------------------------------------------

    def checkinput(self, l):
        """CHECKINPUT: swearing, insults, gibberish, misspelling, tiredness,
        repetition.  Returns a replacement unit, or NIL for normal input."""
        a = NIL
        b = NIL
        self.BADINPUT = NIL
        if ((truthy(self.LOWMAN) and self.INPUTNO >= 20 and self.runtim() >= 60000)
                or (self.INPUTNO >= 30 and is_nil(self.memsizeok()) and is_nil(self.memsizeok()))):
            a = self.choose("TIRED")
            b = ["INTERVIEW", "HAS", "BEEN", "LONG", "ENOUGH"]
            self.addto("PEXIT2", 10)
            self.ENDE = T
            self.error("INPUTNO= " + str(self.INPUTNO) + " SHORT OF SPACE", NIL)
        if is_nil(a):
            b = self.getprop(l, "FX")
            if truthy(b):                              # FX has a few kludges to not allow some inputs
                r = self.errset(lambda: self.lisp.eval(b))
                if truthy(r):
                    b = car(r)
                    if truthy(b):
                        a = b
        if truthy(l) and is_nil(self.getprop(l, "UNIT")) and is_nil(a):
            a = "DONE"
        if is_nil(a) and truthy(assoc("SHIT", self.INPUTQUES)):
            a = self.choose("SWEARING")
            self.BADINPUT = T
            b = "EXPLETIVES"
        if is_nil(a) and (truthy(assoc("CRAZY", self.INPUTQUES)) or truthy(assoc("BAD", self.INPUTQUES))
                          or truthy(assoc("ODD", self.INPUTQUES))):
            self.BADINPUT = T
            b = ["BAD", "ASSOCIATIONS", "WITH", "INPUT", "WORDS"]
        c = self.GIBBERISH - self.OLDGIBB
        d = length(self.SSENT)
        if is_nil(a) and ((c >= 5 and d <= 15) or (c >= 3 and d <= 7) or (c >= 2 and d <= 3)):
            a = self.choose("GIBBERISH")
            b = ["TOO", "MANY", "UNRECOGNIZED", "WORDS"]
        if self.GIBBERISH >= 20:
            self.DO_SPELL = NIL
        if is_nil(a) and self.MISSPELLED >= 6 and self.MISSPELLED - self.OLDMISS >= 3:
            a = self.choose("MISSPELLED")
            b = ["TOO", "MANY", "MISSPELLED", "WORDS"]
        if equal(self.SSENT, append(self.PREV_OUTPUT, ["PD"])) or (truthy(self.PREV_SSENT) and car(self.PREV_SSENT) == "TWICE"
              and equal(cadr(self.PREV_SSENT), self.SSENT)):
            self.addto("PGAMES", 5)
        elif equal(self.PREV_SSENT, self.SSENT):
            self.PREV_SSENT = ["TWICE", self.SSENT]
        else:
            self.PREV_SSENT = self.SSENT
        self.OLDGIBB = self.GIBBERISH
        self.OLDMISS = self.MISSPELLED
        if is_nil(b):
            b = "NORMAL"
        self.window(33, T, b)
        if a == "DONE":
            a = NIL
        return a                                       # NIL if anaph or normal

    def memsizeok(self):
        """MEMSIZEOK: free storage above the limits.  The port has no free-
        storage limit, so this is T unless a test sets ``low_memory``."""
        return NIL if self.low_memory else T

    def runtim(self):
        return self.run_ms

    # -- the belief-driven semantic functions ------------------------------------------

    def apology(self):
        if self.MISTRUST >= 9:
            self.AJUMP = 0.2
        else:
            self.ANGER = self.ANGER - 1
        if is_nil(self.bl("DHOSTILE")) and truthy(self.bl("DDKNOW")):
            return self.choose("SORRY")
        return self.choose("ACCUSE")

    def _guarded(self):
        return (truthy(self.bl("DHOSTILE")) or truthy(self.bl("*DHELPFUL"))
                or truthy(self.bl("DDHARM")))

    def helper(self):
        return self.choose("CAUTION") if self._guarded() else NIL

    def knower(self):
        if truthy(self.bl("DDHARM")) or truthy(self.bl("DHOSTILE")) or truthy(self.bl("*DDHELP")):
            return self.choose("HOSTILEREPLIES")
        if truthy(self.bl("*DTRUSTWORTHY")) or truthy(self.bl("*DHONEST")):
            return self.choose("*DHONEST")
        if truthy(self.bl("DDHELP")):
            return self.choose("DDHELP")
        if truthy(self.bl("DEXCITED")):
            return self.choose("DEXCITED")
        if truthy(self.bl("*DINITIATING")):
            return self.choose("DBAD")
        return NIL

    def leadin(self):
        self.ANAPHLIST = self.ANAPHLISTOLD = NIL
        if truthy(self.DELFLAG):
            return self.delstmt()
        if self.FLARE != "INIT":
            return self.flstmt(self.getprop(self.FLARE, "SET"))
        if self.INTENT == "PINTERACT":
            return self.choose("UPSET")
        return NIL

    def aloof(self):
        return self.choose("ALOOF") if self._guarded() else NIL

    def aloof2(self):
        return self.choose("ALOOF2") if self._guarded() else NIL

    def namecheck(self):
        a = assoc("NAME", self.INPUTQUES)
        if is_nil(a):
            a = assoc("YOU", self.INPUTQUES)
            if truthy(a) and cdr(a) == "YOUR":
                return self.choose("DONTREMEMBER")
        return NIL

    def opinion(self):
        a = NIL
        if truthy(self.bl("DDHARM")) or truthy(self.bl("DHOSTILE")) or truthy(self.bl("*DDHELP")):
            a = self.choose("HOSTILEREPLIES")
        elif truthy(self.bl("*DTRUSTWORTHY")) or truthy(self.bl("*DHONEST")):
            a = self.choose("*DHONEST")
        else:
            for i in ["DABNORMAL", "DEXCITED", "DRATIONAL", "DHELPFUL", "DSOCIABLE"]:
                if truthy(self.bl(i)):
                    a = self.choose(i)
                if truthy(a):
                    break
        return a

    def selffeeling(self):
        if self.ANGER >= 10:
            return self.choose("ANGRY")
        if self.FEAR >= 10:
            return self.choose("FEARFUL")
        if truthy(self.bl("INTHELPFUL")):
            return self.choose("GOOD")
        return NIL

    def interview(self):
        if truthy(self.bl("INTBAD")):
            return self.choose("INTBAD")
        if truthy(self.bl("INTHELPFUL")):
            return self.choose("PRAISE")
        return NIL

    # -- AFFECT / INFEMOTE / INTENTION / DOINTENT ---------------------------------------

    def affect(self):
        """AFFECT: express emotions from the input, current values, topic, beliefs."""
        self.ACTION = NIL
        self.INTENT = NIL
        if truthy(member(self.getprop(self.STOPIC, "SET"), self.SENSITIVELIST)):
            self.AJUMP = 0.2
        self.raise_()
        if self.FEAR >= 18 or self.ANGER >= 18.8:
            self.addto("PEXIT2", 10)
        # the test for activating the paranoid mode
        if ((self.VERSION == "STRONG" and (self.HURT >= 7 or (truthy(self.HJUMP) and self.HJUMP >= 0.1)))
                or (self.VERSION == "MILD" and self.HURT >= 8)):
            self.addto("PPARANOIA", 5)
            self.paranoia()
            self.INTENT = "PPARANOIA"
        elif ((truthy(self.FJUMP) and self.FJUMP >= 0.01) or (truthy(self.AJUMP) and self.AJUMP >= 0.01)
              or self.FEAR >= 14 or self.ANGER >= 14
              or self.STOPIC == "STRONGFEELINGS" or truthy(self.ACTION)):
            self.addto("PSTRONGFEEL", 5)
            self.INTENT = "PSTRONGFEEL"
        for jump, name in (("FJUMP", "FEAR"), ("AJUMP", "ANGER"), ("HJUMP", "SHAME")):
            if truthy(getattr(self, jump)):
                a = self.getprop(jump, "INF")
                note = [name, "RAISED"] + (["FROM", a] if truthy(a) else [])
                self.window(40, T, note)
                if truthy(a):
                    self.putprop(jump, NIL, "INF")
        if is_nil(self.FJUMP) and is_nil(self.AJUMP) and is_nil(self.HJUMP):
            self.window(40, T, ["NO", "CHANGE"])
        if truthy(self.WINDOWS):
            self.wprintvars()
        return self.ACTION

    def infemote(self, bel, l, val):
        """INFEMOTE: an EMOTE rule ((HJUMP 0.5) ...) sets the emotion jump."""
        for a in to_list(l):
            b = car(a)
            c = cadr(a)
            if b == "HJUMP":
                self.PARBEL = cons(bel, self.PARBEL)
            if b == "HJUMP" and truthy(self.WEAK):
                c = c / 2                              # weak paranoia: no strong hurt
            if numberp(val):
                c = c / 2                              # from ADDTO, not ASSERT: weaken
            d = getattr(self, b)
            d = 0 if is_nil(d) else d
            if c >= d:
                self.putprop(b, bel, "INF")
            setattr(self, b, max(d, c))

    def intention(self):
        """INTENTION: the highest-priority intention over its threshold."""
        a = NIL
        for i in to_list(self.INTLIST):
            if self.get0(i, "NTRUTH") >= 5:
                a = self.window(42, NIL, i)
        if is_nil(self.INTENT) or a == "PEXIT" or a == "PEXIT2":
            self.INTENT = a
        self.window(42, NIL, " : " + str(self.INTENT))

    def dointent(self):
        """DOINTENT: perform the current intention; returns an action unit or NIL."""
        self.intention()
        i = self.INTENT
        a = self.getprop(self.INTENT, "TH")
        if truthy(a):
            self.PROVEL = append(self.PROVEL, a)
        self.prove()
        a = self.errset(lambda: self.lisp.apply(i, []) if truthy(i) else NIL)
        if is_nil(a):
            self.error("IN DOINTENT BAD FN", i)
            a = NIL
        else:
            a = car(a)
        self.OLDINTENT = self.INTENT
        self.window(44, T, self.CHOSEN if truthy(self.CHOSEN) else "ANSWER")
        return a

    # -- the intention routines, one per intention -------------------------------------

    def pinteract(self):
        if self.FLARE != "INIT":
            return self.addto("PHELP", 5)
        return NIL

    def pgames(self):
        a = self.choose("GAMES")
        self.addto("PGAMES", -2)
        return a

    def pfacts(self):
        a = self.choose("MOVEON")
        self.addto("PFACTS", -2)
        return a

    def pmafia(self):
        if self.FEAR >= 10:
            a = self.choose("PANIC")
        elif truthy(self.bl("DGAMES")):
            a = NIL
            self.ANGER = self.ANGER - 3
        else:
            a = self.choose("PROBE")
        self.addto("PMAFIA", -2)
        return a

    def phelp(self):
        if truthy(self.DELFLAG):
            return self.addto("PTELL", 5)
        if self.FLARE == "INIT" and (truthy(self.getprop(self.STRUC, "UNIT")) or is_nil(self.REACTTO)
                                     or self.getprop(self.REACTTO, "CLASS") == "LEADIN"):
            self.addto("PHELP", -5)
            return self.flarelead(self.chooselead())
        return NIL

    def pstop(self):
        return NIL

    def ptell(self):
        return NIL

    def pstrongfeel(self):
        return self.strongfeel()

    def pconfirm(self):
        if truthy(self.bl("NDELUSIONS")) and is_nil(self.BADINPUT):
            a = self.choose("PRAISE")
            self.addto("PSTOP", 3)
            return a
        if is_nil(self.BADINPUT) and (truthy(self.getprop(self.REACTTO, "UNIT")) or is_nil(self.REACTTO)):
            a = self.choose("FEELER")
            self.addto("PSTOP", 2)
            self.addto("PCONFIRM", -5)
            return a
        return NIL

    def pself(self):
        a = self.choose("IYOUME")
        self.addto("PSELF", -3)
        return a

    def pexit(self):
        a = self.choose("OPINION")
        self.addto("PEXIT2", 10)
        return a

    def pexit2(self):
        if self.ANGER >= 9:
            g = "MADEXIT"
        elif self.FEAR >= 9:
            g = "FEAREXIT"
        elif is_nil(self.memsizeok()):
            g = "TIRED"
        else:
            g = "EXIT"
        a = self.choose(g)
        self.ENDE = T
        return a

    # PONTOP / PGETBACK / PSUFFER are declared in bel but have no routine in
    # this version; DOINTENT's ERRSET turns the call into a logged error.

    # -- LULL / PPARANOIA / STRONGFEEL / PARANOIA ---------------------------------------

    def lull(self):
        """LULL: is there a lull in the conversation?"""
        if self.OLDTOPIC == "ANAPH" or self.OLDTOPIC == "IYOUME":
            return T
        if length(self.SSENT) >= 10:
            return NIL
        return T if self.random(2) == 1 else NIL

    def pparanoia(self):
        self.addto("PPARANOIA", -5)
        if self.HURT >= 10:
            self.HURT = 10 + (self.HURT - 10) * 3 / 5
        a = assoc(self.getprop(self.REACTTO, "CLASS"), _PARANOIA_CLASS)
        if is_nil(a):
            a = assoc(self.carn(self.getprop(self.REACTTO, "SF")), _PARANOIA_SF)
        if truthy(a):
            a = cadr(a)
        if is_nil(a) and self.STOPIC == "MAFIA":
            a = "AVOIDANCE" if truthy(self.DELFLAG) else "NOMAFIA"
        if is_nil(a) and self.FEAR >= 14:
            # the source tests the unbound variable TYPE here (not STYPE)
            a = "PTHREATQ" if self.TYPE == "Q" else "PAFRAID"
            self.addto("PEXIT", 1)
        if is_nil(a):
            a = "ALIEN" if self.HURT >= 10 else "PHOSTILEREPLIES"
            self.addto("PEXIT", 1)
        return self.choose(a)

    def strongfeel(self):
        """STRONGFEEL: an action to take care of a jump or of high emotions."""
        self.addto("PSTRONGFEEL", -5)
        self.addto("PMAFIA", -5)
        b = NIL
        a = self.getprop(self.REACTTO, "CLASS")
        if is_nil(a):
            pass
        else:
            m = assoc(a, _STRONGFEEL_CLASS)
            if truthy(m):
                b = cadr(m)
            elif a == "DISTRUST":
                b = "TURNOFF" if self.FEAR + self.ANGER >= 14 else "ALOOF"
        if self.ANGER <= 14 and self.FEAR <= 14:
            return self.choose(b)
        if (is_nil(self.FJUMP) and is_nil(self.AJUMP)
                and is_nil(memq(self.STOPIC, ["BYE", "MAFIA", "GAMES", "IYOUME", "FEELINGS", "STRONGFEELINGS"]))):
            return self.fearmode() if self.FEAR >= 14 else self.angermode()
        return self.choose(b)

    def paranoia(self):
        """PARANOIA: project the shame onto distrust of the doctor."""
        a = NIL
        self.assert_belief("*DTRUSTWORTHY")
        for i in to_list(self.PARBEL):
            if truthy(memq(i, ["LYING", "LOSER", "CRAZY", "DUMB"])):
                self.addto(i, -1)
                a = i
        if truthy(a):
            a = assoc(a, _PARANOIA_PROJECT)
            self.assert_belief(cadr(a))
        self.PARBEL = NIL
        return NIL

    # -- the TRACE_MEM windows -------------------------------------------------------------

    _WINDOW_LABELS: ClassVar[dict] = {
        2: "Input:", 3: "Respelled:", 4: "Canonical form:", 5: "Segmented:",
        7: "Simple patterns:", 9: "Result:", 33: "Preprocess:",
        36: "Inferences succeeded:", 37: "New beliefs:", 40: "Emotions:",
        42: "Intentions:", 44: "Action:",
    }

    def window(self, n, flag, l):
        """WINDOW: trace output (TRACEV = ALL prints the labelled windows)."""
        if self.TRACEV == "ALL":
            self.twindow(n, flag, l)
        return l

    def twindow(self, n, flag, l):
        label = self._WINDOW_LABELS.get(n)
        if label is not None and (truthy(flag) or n in (9, 36, 42)):
            self.trace_log.append((label, l))

    def windowset(self, n):
        return n

    def lisp_print(self, x):
        self.trace_log.append(("PRINT", x))
        return x

    def raise_error(self, msg):
        raise LispError(msg)
