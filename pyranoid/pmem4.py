"""The top level and the inference engine (``pmem4``).

Routine-for-routine port of the fourth memory file: PARRY2 (one input),
REACT (one turn of the memory), REACT2 / REACT3 (expressing, and recovering
when a reply set is exhausted), DOSF (running a unit's semantic function),
the anger/fear modes, TOPICANALYZE / HISTORY, and the belief machinery
READBEL / READINF / POSIT / ASSERT / ASSERT2 / ADDTO / PROVE / PROVE2 /
EVALUATE / BL / STATED / INFERENCE.

REACT is the heart of PARRY: preprocess the recognised unit (CHECKINPUT),
resolve anaphora (SPECFN) or take the unit itself (MEMFIND), else scan for
key words (SKEYWD); analyse the topic; run INFERENCE, AFFECT, DOINTENT; if
no intention produced an action, answer the input or punt (MISCQ/MISCS);
run the unit's semantic function (DOSF, twice); express it (REACT2), or
recover (REACT3); rescan the output for flare words (ASCAN); decay the
affects (MODIFVAR) and advance the story lists.
"""

from __future__ import annotations

from pyranoid.lisp import (
    NIL,
    LispError,
    T,
    append,
    atom,
    caddr,
    cadr,
    car,
    cddr,
    cdr,
    cons,
    is_nil,
    lambdaname,
    memq,
    numberp,
    read_file,
    to_list,
    truthy,
)

_ALWAYS_TRY = ["IF730", "IF740", "IF750", "IF760", "IF770", "IF350", "IF380",
               "IF566", "IF884", "IF225"]


class Pmem4Mixin:
    # -- PARRY2: one input sentence through the matcher and the memory ------------------

    def parry2(self):
        """PARRY2: read a sentence, match it, react to it.  Returns the unit."""
        self.BUG = 0
        self.experiment()
        self.BUG = 1
        a = self.errset(self.testm)
        if atom(a):
            self.error(a, "PATTERNMATCH ERROR " + str([self.NEXT_CHAR, self.SSENT, self.INPUTQUES]))
            raise LispError("pattern match error")
        self.BUG = 2
        a = car(a)
        self.PM2INPUT = self.PMINPUT
        self.PMINPUT = a
        if len(to_list(self.SSENT)) == 1:
            a = self.choose("SILENCE")
        self.BUG = 3
        if not lambdaname(a):
            a = NIL
        if truthy(a) and atom(a):
            b = self.getprop(a, "MEQV")
            if truthy(b):
                a = b
        self.REACTINPUT = a
        self.window(9, T, a)
        self.readlambda(a)
        self.window(9, NIL, self.getprop(a, "BONDVALUE"))
        self.BUG = 4
        r = self.errset(lambda: self.react([a, self.q(self.SSENT), self.SSENT]))
        if is_nil(r):
            self.error(a, "ERROR IN REACT " + str(self.SSENT))
        self.BUG = 70
        if truthy(self.ENDE):
            self.modifvar()
        self.BUG = 80
        return a

    def testm(self):
        return self.test_pattern()

    # -- INITB ---------------------------------------------------------------------------------

    def initb(self, data_dir):
        self.oparinitialize(data_dir / "rdata")
        self.readbonds(data_dir / "pdatb")
        self.setupstl()
        self.changel(data_dir / "change")
        self.DELNO = self.BUG = 0
        self.OLDMISS = self.OLDGIBB = 0
        self.INPUTNO = self.REPEATNO = self.SPECFNNO = self.MISCNO = self.NEWTOPICNO = 0
        self.HLIST = self.OLDTOPIC = self.OLDTOPICS = NIL

    # -- REACTPRINT: format the output ----------------------------------------------------------

    def reactprint(self, l):
        sent = l
        if truthy(self.SUPPRESS) and truthy(sent) and not atom(car(sent)):
            sent = cdr(sent)                          # suppress the non-verbal
        self.OUTPUT_TEXT = self.stringate(sent) if truthy(sent) else " "
        self.DIAGNOSTICS = [self.PMINPUT, self.getprop(self.REACTINPUT, "BONDVALUE"),
                            self.TRACE_MEM, self.NEWPROVEN, self.INTENT]
        self.INPUTSSENT = NIL

    # -- DOSF: run a unit's semantic function -------------------------------------------------

    def dosf(self, l):
        """DOSF: EVAL the unit's SF (under ERRSET).  A unit result replaces the
        unit; a non-unit result is the finished output (!OUTPUT) and NIL."""
        def body():
            if lambdaname(l):
                a = self.getprop(l, "SF")
                if truthy(a):
                    a = self.lisp.eval(a)
                    if truthy(a):
                        return a
            return NIL
        b = self.errset(body)
        if atom(b):
            self.error("BAD SF", [l, b])
            return NIL
        b = car(b)
        if not lambdaname(b):
            self.OUTPUT = b
            b = NIL
        return b

    def chooselead(self):
        return ["BOOKIESET", "GAMBLERSET", "HORSERACINGSET", "GANGSTERSET"][self.random(4) - 1]

    def printvars(self):
        line = (f"FEAR = {self.numed(self.FEAR)}  ANGER = {self.numed(self.ANGER)}"
                f"  SHAME = {self.numed(self.HURT)}")
        self.trace_log.append(("VARS", line))

    def wprintvars(self):
        self.printvars()

    # -- ANGERFEARMODE / ANGERMODE / FEARMODE ------------------------------------------------------

    def angerfearmode(self, topic):
        if (truthy(memq(topic, self.getprop("FLARELIST", "SETS")))
                or truthy(memq(topic, ["MAFIA", "BYE", "IYOUME", "STRONGFEELINGS", "FEELINGS", "GAMES"]))):
            return NIL
        self.BUG = 14
        return self.fearmode() if self.FEAR >= 14 else self.angermode()

    def angermode(self):
        return self.choose("ANGER") if self.ANGER > 17.5 else self.choose("HOSTILEREPLIES")

    def fearmode(self):
        if self.FEAR > 18.4:
            self.ENDE = T
            return self.choose("EXIT")
        if (is_nil(self.bl("DDHARM")) and truthy(self.bl("DHELPFUL"))
                and is_nil(self.bl("DMAFIA"))):
            self.FEAR = self.FEAR - 1
            return NIL
        return self.choose("THREATQ") if self.STYPE == "Q" else self.choose("AFRAID")

    # -- TOPICANALYZE / PREVTOPIC / HISTORY -----------------------------------------------------------

    def topicanalyze(self):
        if is_nil(self.STOPIC):
            return NIL
        if truthy(memq(self.STOPIC, ["ANAPH", "FACTS", "STRONGFEELINGS", "GREETINGS"])):
            return NIL
        if self.STOPIC == self.OLDTOPIC:
            return NIL
        self.NEWTOPICNO = self.NEWTOPICNO + 1
        self.OLDTOPICS = cons(self.OLDTOPIC, self.OLDTOPICS)
        self.OLDTOPIC = self.STOPIC
        return self.OLDTOPIC

    def prevtopic(self):
        return memq(self.STOPIC, self.OLDTOPICS)

    def history(self, l):
        """HISTORY: which emotion this input affected (for the next turn's SFs)."""
        if truthy(l):
            return memq(l, self.HLIST)
        self.HLIST = NIL
        if truthy(self.AJUMP) and self.AJUMP >= 0.1:
            self.addh(["AJUMP", "MJUMP"])
        if truthy(self.FJUMP) and self.FJUMP >= 0.1:
            self.addh(["FJUMP", "MJUMP"])
        return NIL

    def addh(self, l):
        for i in to_list(l):
            self.HLIST = cons(i, self.HLIST)

    # -- REACT2 / REACT3 --------------------------------------------------------------------------------

    def react2(self, b):
        """REACT2: enter the input on the conversation list and call REPLYR."""
        self.EXHAUST = NIL
        if not lambdaname(b):
            self.error("NONLAMBDA INTO REACT2", b)
            return NIL
        if truthy(self.OUTPUT):                       # already have a sentence in !OUTPUT
            self.andthen(["IN", b])
            self.andthen(["OUT", NIL])
            return T
        if is_nil(self.diskread(b)):
            self.error("REACT2 ERROR BAD DISKREAD", b)
            return NIL
        self.andthen(["IN", b])
        return self.replyr(b)

    def react3(self, p, struc, sent):
        """REACT3: when the output responses have been exhausted."""
        a = NIL
        b = self.carn(p)
        if is_nil(self.EXHAUST):
            self.error([p, struc, sent], "BAD INPUT IN REACT3")
        if (self.TRACE_MEM == "OK" and self.STOPIC != "STRONGFEELINGS"
                and truthy(self.repetition(b, "IN"))):
            self.REPEATNO = self.REPEATNO + 1
            if is_nil(self.getprop(b, "REPEAT")):
                a = self.get_story()                  # let one repeat go by
            self.putprop(b, T, "REPEAT")
            if is_nil(a):
                a = self.choose("REPEAT")
        if truthy(a) and truthy(self.react2(a)):
            return a
        a = self.get_story()
        if truthy(a) and truthy(self.react2(a)):
            return a
        a = self.exhauster()
        if is_nil(a):
            a = self.choose("EXHAUST")
        if truthy(a) and truthy(self.react2(a)):
            return a
        return NIL

    # -- REACT: the top level of the memory -----------------------------------------------------------

    def react(self, input_):
        struc = car(input_)
        self.STYPE = cadr(input_)
        sent = caddr(input_)
        self.STRUC = struc                            # dynamically visible to PHELP
        self.BUG = 10
        self.INPUTSSENT = cons(self.SSENT, self.INPUTSSENT)
        self.TRACE_MEM = NIL
        self.INPUTNO = self.INPUTNO + 1
        self.ANAPHLISTNEW = self.EXHAUST = NIL
        self.OUTPUT = self.WDFLAG = NIL
        self.CHOSEN = NIL
        if truthy(self.DOC_NAME_FLAG):
            self.DOCNAME = self.getdocname()
        self.BUG = 11
        if self.INPUTNO == 2 and is_nil(self.ERRNAME):
            self.ERRNAME = T
        self.BUG = 12
        if truthy(struc) and is_nil(self.readlambda(struc)):
            self.REACTTO = struc = NIL
            self.TRACE_MEM = "NOT_IN_MEMORY"
        self.window(51, T, self.getprop(struc, "TOPIC"))
        a = self.getprop(struc, "UNIT")
        if truthy(a):
            self.window(52, T, a)

        self.window(31, T, "PREPROCESS")
        self.REACTTO = self.checkinput(struc)         # preprocess the input
        if truthy(self.REACTTO) and is_nil(self.readlambda(self.REACTTO)):
            self.REACTTO = struc = NIL
        self.BUG = 14
        if is_nil(self.REACTTO) and truthy(struc):
            self.REACTTO = self.specfn(struc)         # look for anaphora
            if truthy(self.REACTTO):
                self.TRACE_MEM = "SPECIALANAPH"
                self.SPECFNNO = self.SPECFNNO + 1
            else:
                self.REACTTO = self.memfind(struc)    # look up normal input
                if truthy(self.REACTTO):
                    self.TRACE_MEM = "OK"
        if self.REACTTO == "QUIT":
            self.REACTTO = NIL
            self.TRACE_MEM = "NOSPECIALANAPH"
        if is_nil(self.readlambda(self.REACTTO)):
            self.REACTTO = NIL
        self.BUG = 15
        if is_nil(self.REACTTO) and is_nil(self.DELFLAG):
            self.REACTTO = self.skeywd(self.STYPE, self.INPUTQUES)
            if truthy(self.REACTTO):
                self.TRACE_MEM = "KEYWORD"
        if is_nil(self.readlambda(self.REACTTO)):
            self.REACTTO = NIL
        self.BUG = 16

        self.STOPIC = self.carn(self.getprop(struc, "TOPIC"))
        self.topicanalyze()
        self.window(31, T, "INFERENCES")
        if is_nil(self.errset(self.inference)):
            self.error("INFERENCE ERROR", self.PROVEL)
        self.window(31, T, "AFFECTS")
        if is_nil(self.errset(self.affect)):
            self.error("AFFECT ERROR", self.ACTION)
        self.window(31, T, "INTENTIONS")
        found = NIL
        r = self.errset(self.dointent)
        if is_nil(r):
            self.error("DOINTENT", self.INTENT)
        else:
            found = car(r)
        if truthy(found):
            self.TRACE_MEM = "INTENT"
        self.window(31, T, "ACTIONS")
        self.BUG = 17
        if is_nil(found) and truthy(self.REACTTO):
            found = self.REACTTO
        # nothing in FOUND: punt and take a miscellaneous response
        if is_nil(found):
            found = self.miscq(sent) if self.STYPE == "Q" else self.miscs(sent)
            self.MISCNO = self.MISCNO + 1
            if is_nil(self.TRACE_MEM) and truthy(found):
                self.TRACE_MEM = "NO_PATTERN"
        self.BUG = 18
        if is_nil(self.readlambda(found)):
            found = NIL
        self.BUG = 20

        self.REACTTO = found
        # do the semantic function; the result is a ^H name or an actual sentence
        b = self.dosf(found)
        if truthy(b):
            a = self.dosf(b)
            found = a if truthy(a) else b
        self.BUG = 22

        if self.not_last_input():                     # another sentence on the input line
            return NIL

        if self.carn(self.getprop(found, "TOPIC")) == "MAFIA":
            self.DELNO = self.DELNO + 1               # number of delusion statements
        self.react2(found)                            # the English sentence into !OUTPUT
        self.BUG = 30
        found2 = NIL
        if is_nil(self.OUTPUT):
            found2 = self.react3(found, struc, sent)  # try again to get output
        self.BUG = 35
        self.ANAPHLISTOLD = self.ANAPHLIST
        self.ANAPHLIST = self.ANAPHLISTNEW
        # rescan the output for flare and delusional words
        if (truthy(self.OUTPUT) and truthy(car(self.OUTPUT))
                and is_nil(self.errset(lambda: self.ascan(self.canona(self.OUTPUT), NIL) or T))):
            self.error("ASCAN " + str(self.OUTPUT), found)
        self.BUG = 40
        self.LAST_OUTPUT = found
        self.BUG = 42
        self.window(31, T, "OUTPUT")
        self.PREV_OUTPUT = self.OUTPUT
        self.window(49, T, self.OUTPUT if atom(car(self.OUTPUT)) else cdr(self.OUTPUT))
        if is_nil(self.errset(lambda: self.reactprint(self.OUTPUT) or T)):
            self.error("REACTPRINT", found)
        self.INPUTSSENT = NIL
        self.BUG = 48

        def bottom():
            self.history(NIL)                         # remember for the next turn's SFs
            self.modifvar()                           # update the emotion variables
            if truthy(self.WINDOWS):
                self.wprintvars()
            # update the story lists
            if lambdaname(self.LAST_OUTPUT):
                a = self.getprop(self.LAST_OUTPUT, "STORYNAME")
                if truthy(a):
                    self.deletep(a, self.LAST_OUTPUT, "STORY")
            if lambdaname(found2):
                a = self.getprop(found2, "STORYNAME")
                if truthy(a):
                    self.deletep(a, found2, "STORY")
            return T
        if is_nil(self.errset(bottom)):
            self.error("ERROR FROM BOTTOM OF REACT", found)
        self.BUG = 50
        return found

    # -- BINIT / READBEL / READINF ------------------------------------------------------------------

    def binit(self, data_dir):
        self.INTLIST = self.INTENT = self.PROVEN = self.PROVEL = NIL
        self.PRINTALL = NIL
        self.readbel(data_dir / "bel")
        self.readinf(data_dir / "inf")

    def readbel(self, path):
        """READBEL: (NAME NUMBER CLASS [OPPOS NUMBER]) -> NTRUTH, CLASS, OPPOS."""
        for a in read_file(path):
            if not isinstance(a, list):
                continue
            self.putprop(car(a), cadr(a), "NTRUTH")
            if caddr(a) == "INN":
                self.INTLIST = cons(car(a), self.INTLIST)
                self.putprop(car(a), caddr(a), "CLASS")
            b = cdr(cddr(a))
            if truthy(b):
                self.putprop(car(b), cadr(b), "NTRUTH")
                self.putprop(car(b), car(a), "OPPOS")
                self.putprop(car(a), car(b), "OPPOS")
        self.INTLIST = list(reversed(to_list(self.INTLIST))) or NIL

    def readinf(self, path):
        """READINF: TH2 / EMOTE hooks onto their units and beliefs; theorems
        with back-pointers (TH) from each atomic antecedent."""
        for a in read_file(path):
            if not isinstance(a, list):
                continue
            if truthy(memq(car(a), ["TH2", "EMOTE"])):
                for i in to_list(cddr(a)):
                    self.putprop(i, cons(cadr(a), self.getprop(i, car(a))), car(a))
            else:
                if truthy(self.getprop(car(a), "THEOREM")):
                    self.lisp_print(["DUPLICATE", "INF:", car(a)])
                self.putprop(car(a), cons(cadr(a), caddr(a)), "THEOREM")
                for i in to_list(caddr(a)):
                    if atom(i):
                        self.putprop(i, cons(car(a), self.getprop(i, "TH")), "TH")

    # -- POSIT / ASSERT / ASSERT2 / ADDTO / GET0 / PROVE / PROVE2 / EVALUATE / BL --------------

    def posit(self, b):
        if atom(b):
            return self.assert2(b)
        return self.addto(car(b), cadr(b))

    def assert_belief(self, b):
        """ASSERT: assert B and prove its consequences."""
        self.assert2(b)
        return self.prove()

    def assert2(self, b):
        """ASSERT2: assert a new belief; queue the theorems it is an antecedent of."""
        a = self.getprop(b, "EMOTE")
        if truthy(a):
            self.infemote(b, a, T)
        a = self.getprop(b, "OPPOS")
        if truthy(self.getprop(b, "TRUTH")):
            return T
        if truthy(a) and truthy(self.getprop(a, "TRUTH")):     # opposite already true
            return T
        self.window(37, NIL, b)
        self.putprop(b, T, "TRUTH")
        if truthy(a):
            self.putprop(a, NIL, "TRUTH")                      # unassert the opposite
        a = self.getprop(b, "TH")
        if truthy(a):
            self.PROVEL = append(self.PROVEL, a)
        self.PROVEN = cons(b, self.PROVEN)
        self.NEWPROVEN = cons(b, self.NEWPROVEN)
        return NIL

    def addto(self, b, n):
        """ADDTO: add to a belief's NTRUTH; assert it if the threshold is crossed."""
        a = self.getprop(b, "EMOTE")
        if truthy(a):
            self.infemote(b, a, n)
        a = self.getprop(b, "TH2")
        if truthy(a):
            for i in to_list(a):
                self.addto(i if atom(i) else car(i), self.quo(n, 2))
        a = self.getprop(b, "OPPOS")
        if truthy(self.getprop(b, "TRUTH")) or (truthy(a) and truthy(self.getprop(a, "TRUTH"))):
            return T
        self.window(37, NIL, [b, n])
        val = n + self.get0(b, "NTRUTH")
        if self.getprop(b, "CLASS") == "INN":
            if val >= 10:
                val = 9
            elif val <= 0:
                val = 0
        self.putprop(b, val, "NTRUTH")
        if val >= 10:
            self.assert2(b)
        return NIL

    def get0(self, i, v):
        a = self.getprop(i, v)
        return a if numberp(a) else 0

    @staticmethod
    def quo(a, b):
        """MLISP ``/``: fixnum division truncates toward zero."""
        if isinstance(a, int) and isinstance(b, int):
            return int(a / b)
        return a / b

    def prove(self):
        while truthy(self.PROVEL):
            self.prove2(car(self.PROVEL))
            self.PROVEL = cdr(self.PROVEL)
        return NIL

    def prove2(self, th):
        a = self.getprop(th, "THEOREM")
        if is_nil(a):
            return NIL
        b = self.carn(car(a))
        if truthy(self.bl(b)):                                 # already proven
            return NIL
        self.window(35, T, a)
        c = car(a)
        b = T
        for i in to_list(cdr(a)):
            if is_nil(b):
                break
            b = self.evaluate(i)
        if truthy(b):
            self.posit(c)
            self.window(36, T, a)
        return NIL

    def evaluate(self, i):
        if atom(i):
            return self.stated(i) if lambdaname(i) else self.bl(i)
        if car(i) == "NOT":
            return NIL if truthy(self.bl(cadr(i))) else T
        return self.lisp.eval(i)

    def bl(self, b):
        """BL: is belief B true, or intention B over its threshold?"""
        if not atom(b):
            self.error("BL NOT ATOM", b)
            return NIL
        if self.getprop(b, "CLASS") == "INN":
            return T if self.get0(b, "NTRUTH") >= 5 else NIL
        return self.getprop(b, "TRUTH")

    def stated(self, i):
        return T if self.REACTTO == i else NIL

    def inference(self):
        """INFERENCE: prove all that can be proved from this input."""
        self.NEWPROVEN = NIL
        self.PARA = T if self.MISTRUST > 7 else NIL            # the paranoid parameter
        if self.STOPIC == "GREETINGS":
            self.SPECFNNO = self.SPECFNNO + 1
        self.SPECFNRA = self.quo(100 * self.SPECFNNO, self.INPUTNO)
        self.PROVEL = list(_ALWAYS_TRY)                        # try these every time
        if truthy(self.DOC_NAME_FLAG):
            self.PROVEL = cons("IF331", self.PROVEL)
        if self.STOPIC == "MAFIA":
            self.PROVEL = cons("IF888", self.PROVEL)
        a = self.getprop(self.REACTTO, "TH")                   # the input's own inferences
        if truthy(a):
            self.PROVEL = append(self.PROVEL, a)
        a = self.getprop(self.REACTTO, "TH2")
        if truthy(a):
            for i in to_list(a):
                self.posit(i)
        self.prove()
        return T
