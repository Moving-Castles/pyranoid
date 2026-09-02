"""The paranoid model of "old PARRY": flares, delusions, reply groups.

A routine-for-routine port of ``opar3`` (the surviving pieces of the 1971
program that the 1974 memory-based PARRY kept for its flare and delusion
handling), on the shared property-list image.  Routine names are the
original ones; the order follows the source file.

Terms: a *flare* is a topic on the path toward the Mafia delusion (horses ->
horse racing -> bookies -> rackets -> Mafia); each flare set has trigger
WORDS, a WT weight, a NEXT pointer one step closer to the Mafia, and a STORY
of units to tell.  ``FLARE`` holds the current flare *word* ('INIT for none);
``GET(FLARE,'SET)`` is its set.  ``DELFLAG`` means the delusion itself is
under discussion; ``DELEND`` that PARRY is through with it.
"""

from __future__ import annotations

from pyranoid.lisp import (
    NIL,
    T,
    append,
    assoc,
    atom,
    cadr,
    car,
    cdr,
    cons,
    delete,
    explode,
    is_nil,
    last,
    member,
    read_file,
    to_list,
    truthy,
)


class OparMixin:
    # -- OPARINITIALIZE: evaluate RDATA and set the model's variables --------

    def oparinitialize(self, rdata_path) -> None:
        for form in read_file(rdata_path):
            self.lisp.eval(form)
        self.FLARE = "INIT"                                  # current flare topic; 'INIT = none
        self.LIVEFLARES = self.getprop("FLARELIST", "SETS")  # flares not yet discussed
        self.DEADFLARES = NIL
        self.SENSITIVELIST = self.getprop("SENSITIVELIST", "SETS")
        self.DELNLIST = self.getprop("DELWDS", "NOUNS")      # delusion topics
        self.DELVLIST = self.getprop("DELWDS", "VERBS")
        self.DELALIST = self.getprop("DELWDS", "AMBIG")      # only above a mistrust threshold
        self.ANGER = self.ANGER0 = self.FEAR = self.FEAR0 = 0
        self.MISTRUST = self.MISTRUST0 = self.HURT = self.HURT0 = 0
        self.FJUMP = self.AJUMP = self.HJUMP = NIL

    # -- CHECKFLARE: the highest-weight flare word in the input ---------------

    def checkflare(self, inp, flarelist, flag):
        """Scan INPUTQUES pairs for flare words drawn from ``flarelist``.

        Records the strongest in FLARE/WEIGHT (ignoring a very weak new one
        while a flare is already under discussion) and, if ``flag``, marks the
        surface word USED.  Returns T if a flare was recorded.
        """
        nflare = "INIT"
        result = NIL
        w = NIL
        wt = NIL
        for word in to_list(inp):
            fset = self.getprop(car(word), "SET")
            if truthy(member(fset, flarelist)) and is_nil(self.getprop(cdr(word), "USED")):
                wt = self.getprop(fset, "WT")
                if wt > self.getprop(self.getprop(nflare, "SET"), "WT"):
                    nflare = car(word)
                    result = T
                    w = cdr(word)
        if truthy(result):
            wt = self.getprop(self.getprop(nflare, "SET"), "WT")
            if self.FLARE != "INIT" and not wt > 1:
                result = NIL
            else:
                self.FLARE = nflare
                self.WEIGHT = wt                       # used in computing the rise in fear
                if truthy(w) and truthy(flag):
                    self.putprop(w, T, "USED")
        return result

    # -- DELREF: a direct reference to the delusional complex ----------------

    def delref(self, found):
        """Enter (or deepen) delusional discussion; returns a reply only when
        the delusions are used up (MAFIAEND) and finished with."""
        result = NIL
        # The source reads ``IF % FOUND AND % NOT (FOUND = 'MAFIAEND)``: the
        # FOUND guard is commented out, so a NIL argument takes this branch.
        if found != "MAFIAEND":
            if truthy(self.DELFLAG):
                # delusions already under discussion: strong vs ambiguous topic
                if truthy(found) and truthy(self.getprop(car(found), "STRONG")):
                    self.FJUMP = 0.4
                else:
                    self.FJUMP = 0.1
            else:
                self.FJUMP = 0.5
                self.putprop("MAFIA", T, "USED")       # 'MAFIA no longer induces fear
                self.flmod("MAFIASET")
            if is_nil(self.DELEND):
                self.DELFLAG = T
            self.FLARE = "INIT"                        # lower-priority flares recognised again
            self.TOPIC = "DELUSIONS"
            result = NIL
        elif found == "MAFIAEND" and truthy(self.DELEND):
            result = self.choose("MAFIASET")
        return result

    # -- DELSTMT: the next delusion ------------------------------------------

    def delstmt(self):
        if truthy(self.WEAK):                          # weak version: rackets, not Mafia
            return self.flstmt("RACKETSET")
        if is_nil(self.getprop("DELNSET", "STORY")):
            # Source: ``IF NOT GET('DELNSET,'STORY) THEN DELFLAG NIL ALSO
            # CHOOSE 'MAFIASET;`` -- no RETURN, so execution continues below
            # and DELFLAG is set again; the chosen reply is discarded.
            self.DELFLAG = NIL
            self.choose("MAFIASET")
        self.DELFLAG = T
        self.FLARE = "INIT"
        self.TOPIC = "DELUSIONS"
        return self.choosedel(NIL)

    # -- FLAREREF: handle flare references -------------------------------------

    def flareref(self, inp):
        if truthy(self.checkflare(inp, self.LIVEFLARES, NIL)):   # new flare: record as old
            self.flrecord(self.getprop(self.FLARE, "SET"))
        if truthy(self.checkflare(inp, self.DEADFLARES, T)):     # old flare: respond to it
            return self.getprop(self.FLARE, "SET")
        return NIL

    # -- ASCAN: scan PARRY's own answer for flare / Mafia mentions -------------

    def ascan(self, ans, q):
        if truthy(self.checkflare(ans, self.LIVEFLARES, T)):
            self.putprop(self.getprop(self.FLARE, "SET"), T, "USED")
        if truthy(member("MAFIA", ans)):
            self.DELFLAG = T
            self.FLARE = "INIT"
            self.TOPIC = "DELUSIONS"
        if truthy(self.DELFLAG):
            self.delcheck(ans)
        return NIL

    # -- CHOOSE: the next reply unit of a named group ---------------------------

    def choose(self, replies):
        if is_nil(replies):
            return NIL
        self.CHOSEN = replies
        response = self.getprop(replies, "IND")
        if is_nil(response):
            if replies == "EXHAUST":
                self.ENDE = T
                return self.choose("BYEFEDUP")
            return self.choose("EXHAUST")
        return response

    def choosedel(self, type_):
        semant = self.getprop("DELNSET", "STORY")
        return car(semant) if truthy(semant) else NIL

    # -- DELCHECK: new delusion expressions in the input -----------------------

    def delcheck(self, inp):
        words_ = self.member3(self.DELNLIST, inp)
        if is_nil(words_):
            words_ = self.member3(self.DELVLIST, inp)
        if is_nil(words_) and self.MISTRUST > 10:
            words_ = self.member3(self.DELALIST, inp)
        if truthy(words_) and truthy(cdr(words_)):
            self.putprop(cdr(words_), T, "USED")
        if truthy(words_) and atom(words_):
            words_ = cons(words_, NIL)
        if truthy(self.member3("MAFIA", inp)) and is_nil(words_):
            words_ = "MAFIAEND"
        return words_

    def deletep(self, l, wd, prop):
        self.putprop(l, delete(wd, self.getprop(l, prop)), prop)

    # -- flare bookkeeping: FIXPTRS, FLRECORD, FLMOD ---------------------------

    def fixptrs(self, flset):
        for concept in to_list(append(self.LIVEFLARES, self.DEADFLARES)):
            if self.getprop(concept, "NEXT") == flset:
                self.putprop(concept, self.getprop(flset, "NEXT"), "NEXT")

    def flrecord(self, flset):
        self.flmod(flset)
        self.FJUMP = self.WEIGHT / 40.0
        self.TOPIC = flset

    def flmod(self, flset):
        self.LIVEFLARES = delete(flset, self.LIVEFLARES)
        self.DEADFLARES = cons(flset, self.DEADFLARES)
        self.fixptrs(flset)

    # -- FLARELEAD: introduce a flare concept ------------------------------------

    def flarelead(self, flset):
        self.putprop(flset, T, "USED")
        if self.getprop(flset, "TYPE") == "INSTITUTION":
            self.WDFLAG = ["THE", car(self.getprop(flset, "WORDS"))]
        elif car(last(explode(self.FLARE))) == "S":        # keep a plural flare word
            self.WDFLAG = [self.FLARE]
        else:
            self.WDFLAG = [car(self.getprop(flset, "WORDS"))]
        they = cadr(self.WDFLAG) if truthy(cdr(self.WDFLAG)) else car(self.WDFLAG)
        self.addanaph([cons("THEY", they)])
        self.addanaph([cons("GO_ON", self.carn(self.getprop(flset, "STORY")))])
        return self.choose("NEXTFL")

    # -- FLSTMT / LEADON: the next statement about a flare ----------------------

    def flstmt(self, fset):
        if fset == "MAFIASET" and is_nil(self.DELEND):    # reached the Mafia: delusional mode
            self.DELFLAG = T
            return self.delstmt()
        stmt = self.getprop(fset, "STORY")
        if truthy(stmt):
            return car(stmt)
        return self.leadon(fset)

    def leadon(self, oldset):
        newset = self.getprop(oldset, "NEXT")
        if newset != "MAFIASET":
            self.flmod(oldset)                           # mark the old one used up
            self.FLARE = car(self.getprop(newset, "WORDS"))
        elif truthy(self.DELEND):                        # at the Mafia but through with delusions
            self.FLARE = "INIT"
            return self.choose("FEELER")
        elif (truthy(self.WEAK) or self.FEAR > 17 or self.ANGER > 17
              or self.FEAR + self.ANGER + self.MISTRUST > 40):
            return self.choose("CHANGESUBJ")             # unwilling to discuss the Mafia
        else:
            delete("MAFIA", self.DELNLIST)               # (result discarded in the source too)
            self.DELFLAG = T
            self.FLARE = "INIT"
            self.TOPIC = "DELUSIONS"
        if truthy(self.getprop(newset, "USED")):         # no leading statement twice
            return self.flstmt(newset)
        return self.flarelead(newset)

    # -- MEMBER3: are any of the words in the input (an INPUTQUES alist)? ------

    def member3(self, wlist, l):
        if atom(wlist):
            wlist = [wlist]
        pair = NIL
        for word in to_list(wlist):
            pair = assoc(word, l)
            if truthy(pair) and truthy(self.getprop(cdr(pair), "USED")):
                pair = NIL
            if truthy(pair):
                break
        return pair

    # -- MISCQ / MISCS: fall-back answers to unrecognised questions/statements --

    def miscq(self, q):
        ans = NIL
        if truthy(member("HOW", q)):                     # unidentifiable "how" question
            for concept in ["MANY", "MUCH", "LONG", "OFTEN"]:
                if truthy(member(concept, q)):
                    ans = self.choose(concept)
                    if truthy(ans):
                        break
        if truthy(ans):
            return ans
        ans = self.speconcept(q)                         # answer according to context
        if truthy(ans):
            return ans
        if self.FLARE != "INIT" and truthy(self.lull()):
            ans = self.flstmt(self.getprop(self.FLARE, "SET"))
            if truthy(ans):
                return ans
        if truthy(self.DELFLAG) and truthy(self.lull()):
            ans = self.delstmt()
            if truthy(ans):
                return ans
        if truthy(member("WHY", q)):                      # wh- questions
            ans = self.choose("WHY")
        else:
            for qword in to_list(self.getprop("QLIST", "IND")):
                ans = self.choose("UNKNOWN") if truthy(member(qword, q)) else NIL
                if truthy(ans):
                    break
        if truthy(ans):
            return ans
        if truthy(member("TELL", q)):                     # miscellaneous "tell" question
            return self.choose("KNOWNOTHING")
        return self.choose("QREPLIES")                    # no clues: noncommittal

    def miscs(self, s):
        if truthy(member("JUMP", s)):
            self.ENDE = T
            return self.choose("EXIT")
        if car(s) in ("HI", "HELLO") or truthy(member(cadr(s), ["MORNING", "AFTERNOON", "EVENING"])):
            return self.choose("HELLO")
        if ((truthy(member("ALREADY", s)) or truthy(member("BEFORE", s)))
                and (truthy(member("SAID", s)) or truthy(member("MENTIONED", s)))):
            return self.choose("ALREADYSAID")
        ans = self.speconcept(s)                           # the context of the conversation
        if truthy(ans):
            return ans
        if self.FLARE != "INIT" and truthy(self.lull()):
            ans = self.flstmt(self.getprop(self.FLARE, "SET"))
            if truthy(ans):
                return ans
        if truthy(self.DELFLAG) and truthy(self.lull()):
            ans = self.delstmt()
            if truthy(ans):
                return ans
        return self.choose("SREPLIES")                     # noncommittal reply

    # -- MODIFVAR: the affect variables after each I-O pair --------------------

    def modifvar(self):
        self.ANGER = self.lmax(self.ANGER - 1, self.ANGER0)
        self.HURT = self.lmax(self.HURT - 0.5, self.HURT0)
        if truthy(self.DELFLAG):
            self.FEAR = self.lmax(self.FEAR - 0.1, self.FEAR0 + 5)     # +5 floor under delusions
        elif self.FLARE != "INIT":
            self.FEAR = self.lmax(self.FEAR - 0.2, self.FEAR0 + 3)     # +3 floor under flares
        else:
            self.FEAR = self.lmax(self.FEAR - 0.3, self.FEAR0)
        self.MISTRUST = self.lmax(self.MISTRUST - 0.05, self.MISTRUST0)
        if truthy(self.TRACEV):
            self.printvars()
        self.FJUMP = NIL
        self.AJUMP = NIL
        self.HJUMP = NIL

    @staticmethod
    def lmax(l, m):
        """MAX (opar3): ``IF L >= M THEN L ELSE M``."""
        return max(l, m)
