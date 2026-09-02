"""The memory layer: expressing units, anaphora, stories (``pmem``).

Routine-for-routine port of the first memory file:

* BEL / ENG link PDAT records into the property-list memory (a #B record
  puts BONDVALUE and every KEYWORD VALUE pair on the ^H atom; a #E record
  puts ANAPH, EXH and the sentence classes on the ^B atom).
* REPLYR / EXPRESS / SELSENTENCE / SAY turn a chosen ^H unit into words,
  consuming the sentence said (each sentence is said at most once) and
  handling embedded references ``((2 RESP NORMAL))`` into a bond's slots.
* ANDTHEN keeps the conversation list; ADDANAPH the anaphora lists.
* SPECFN / GO_ON / ELAB / WHO / WHAT / GENL / GET_ANAPH resolve anaphoric
  inputs against what was last said, falling back to GET_STORY, which tells
  the next line of the current topic's story.
* SETUPSTL, READBONDS, CHANGEL load the auxiliary tables.

Two authentic quirks are reproduced rather than repaired: ANDTHEN never
sets !LASTIN/!LASTOUT (the source assigns an unset local), and REPETITION
compares a conversation-list entry with an atom, so it never finds a repeat.
"""

from __future__ import annotations

from pyranoid.lisp import (
    NIL,
    Pair,
    T,
    append,
    assoc,
    atom,
    caddr,
    cadr,
    car,
    cddr,
    cdr,
    cons,
    deleten,
    equal,
    is_nil,
    lambdaname,
    length,
    member,
    memq,
    nth,
    numberp,
    read_file,
    to_list,
    truthy,
)


class PmemMixin:
    # -- DISKREAD, READLAMBDA, CARN ---------------------------------------------

    def readlambda(self, a):
        """READLAMBDA: is ``a`` a unit id that the memory can read?"""
        if not lambdaname(a):
            return NIL
        if truthy(self.diskread(a)):
            return T
        self.error("BAD DISKREAD", a)
        return NIL

    def diskread(self, name):
        """DISKREAD: the unit is in core (PDAT is preloaded; NIL = not there)."""
        return T if truthy(self.getprop(name, "INCORE")) else NIL

    @staticmethod
    def carn(l):
        return l if atom(l) else car(l)

    # -- BEL / ENG: link a PDAT record into memory -------------------------------

    def load_pdat(self, path) -> None:
        """Read the whole memory file, linking each record as DISKREAD would."""
        from pathlib import Path

        from pyranoid.lisp import decode_bytes, normalise_glyphs, read_forms

        text = normalise_glyphs(decode_bytes(Path(path).read_bytes()))
        mk = text.find("ENDMK")                    # the SAIL editor's directory page
        if mk != -1:
            ff = text.find("\f", mk)
            text = text[ff + 1:] if ff != -1 else text[mk + 5:]
        for form in read_forms(text):
            if not isinstance(form, list):
                continue
            if car(form) == "#B":
                name = self.bel(cdr(form))
            elif car(form) == "#E":
                name = self.eng(cdr(form))
            else:
                continue  # (*** comment ***)
            if truthy(name):
                self.putprop(name, T, "INCORE")

    def bel(self, x):
        """BEL: (^H17 100 (LOC I HOSP) KEY VAL ...) -> properties of ^H17."""
        name, truth, unit = car(x), cadr(x), caddr(x)
        if is_nil(x) or is_nil(cdr(x)) or is_nil(cddr(x)) or not numberp(truth):
            self.error("B BAD INPUT", x)
            return NIL
        if truthy(self.getprop(name, "BONDVALUE")):
            self.error("BAD INPUT-DOUBLE ENTRY", name)
        self.putprop(name, unit, "BONDVALUE")
        x = cdr(x)
        while True:
            x = cddr(x)
            if is_nil(x):
                break
            if not atom(car(x)) or is_nil(cdr(x)):
                self.error("BAD INPUT ", name)
                return NIL
            self.putprop(name, cadr(x), car(x))
        return name

    def eng(self, x):
        """ENG: (^B23 [ANAPH ..] [EXH ..] NORMAL (...) ...) -> properties of ^B23."""
        if is_nil(x) or is_nil(cdr(x)) or is_nil(cddr(x)):
            self.error("E BAD INPUT", x)
            return NIL
        unit = car(x)
        if truthy(self.getprop(unit, "NORMAL")) or truthy(self.getprop(unit, "EMBQ")):
            self.error("BAD INPUT-DOUBLE ENTRY", unit)
        x = cdr(x)
        if car(x) == "ANAPH":
            self.putprop(unit, cadr(x), "ANAPH")
            x = cddr(x)
        if car(x) == "EXH":
            self.putprop(unit, cadr(x), "EXH")
            x = cddr(x)
        while True:
            if is_nil(x) or is_nil(cdr(x)) or atom(cdr(x)) or not atom(car(x)):
                self.error("E BAD INPUT", unit)
                return NIL
            self.putprop(unit, cadr(x), car(x))
            x = cddr(x)
            if is_nil(x):
                break
        if is_nil(self.getprop(unit, "NORMAL")):
            self.error("NO NORMAL SENTS", unit)
        return unit

    # -- REPLYR, ANDTHEN, EXPRESS, SELSENTENCE, SAY ---------------------------------

    def replyr(self, semant):
        """REPLYR: select and express an output sentence for a ^H unit."""
        if is_nil(semant):
            self.error(NIL, "NOSEMANT IN REPLYR")
            return NIL
        self.andthen(["OUT", semant])
        a = self.express(semant, "RESP")
        if truthy(a) and truthy(self.WDFLAG):
            self.OUTPUT = append(a, self.lastword(self.WDFLAG))
        else:
            self.OUTPUT = a
        self.WDFLAG = NIL
        return self.OUTPUT

    def andthen(self, thing):
        """ANDTHEN: put (IN unit) / (OUT unit) on the conversation list."""
        a = NIL
        if self.LAST_ANDTHEN == car(thing):
            return NIL
        self.CLIST = cons(thing, self.CLIST)
        if car(thing) == "IN":
            self.LASTIN = a          # sic: the source assigns the unset local A
        elif car(thing) == "OUT":
            self.LASTOUT = a
        self.LAST_ANDTHEN = car(thing)
        return car(self.CLIST)

    def express(self, semant, cls):
        """EXPRESS: say SEMANT using sentence class CLS (RESP), resolving the
        class through the bond's predicate unit if the unit has none."""
        self.diskread(semant)
        a = self.getprop(semant, cls)
        bond = self.getprop(semant, "BONDVALUE")
        if is_nil(a) and truthy(bond):
            c = self.getprop(car(bond), "UNIT")
            if truthy(c) and truthy(self.diskread(c)):
                a = self.getprop(c, cls)
        if is_nil(a):
            a = self.getprop(semant, "RESP")
            if is_nil(a):
                self.error("NO CLASS " + str(cls), semant)
                return NIL
        k = self.getprop(semant, "ANAPH")
        if truthy(k):
            self.addanaph(k)
        a = self.selsentence(a)
        return self.say(a, cdr(bond)) if truthy(a) else NIL

    def selsentence(self, unit):
        """SELSENTENCE: pick one NORMAL sentence of a ^B unit (in order if
        EXH, else at random), delete it from memory, add its anaphora."""
        cls = "NORMAL"
        if is_nil(self.diskread(unit)):
            return NIL
        a = self.getprop(unit, cls)
        anaph = self.getprop(unit, "ANAPH")
        sents = a
        if is_nil(sents):
            self.EXHAUST = T
            return NIL
        n = 1 if truthy(self.getprop(unit, "EXH")) else self.random(length(sents))
        s = nth(sents, n)
        self.putprop(unit, deleten(sents, n), cls)
        if atom(anaph) and truthy(anaph):
            anaph = self.lisp.eval(anaph)
        self.addanaph(anaph)
        return s

    def say(self, l, args):
        """SAY: a sentence, or an embedded reference (index class) into ARGS."""
        if not atom(car(l)) and numberp(car(car(l))):
            return self.express(nth(args, car(car(l))), cadr(car(l)))
        return l

    # -- ADDANAPH ---------------------------------------------------------------------

    def addanaph(self, l):
        """ADDANAPH: merge (anaphor . unit) pairs into !ANAPHLISTNEW."""
        for i in to_list(l):
            a = assoc(car(i), self.ANAPHLISTNEW)
            if truthy(a):
                if isinstance(a, Pair):
                    a.cdr = cdr(i)           # RPLACD
                else:
                    a[1:] = to_list(cdr(i))
            else:
                self.ANAPHLISTNEW = cons(i, self.ANAPHLISTNEW)
        return self.ANAPHLISTNEW

    # -- SPECFN and the anaphora routines ------------------------------------------

    def specfn(self, struc):
        """SPECFN: if the input is an anaphor, resolve it; 'QUIT if it could not be."""
        name = self.getprop(struc, "UNIT")
        if is_nil(name):
            return NIL
        if truthy(member(name, ["GO_ON", "ELAB", "WHO", "WHAT"])):
            a = self.errset(lambda: getattr(self, name.lower())(NIL, T))
            if atom(a):
                self.error("SPECFN", name)
                a = NIL
            else:
                a = car(a)
            return a if truthy(a) else "QUIT"
        if truthy(assoc(name, self.ALLANAPHS)):
            a = self.genl(struc, T, name)
            return a if truthy(a) else "QUIT"
        return NIL

    def go_on(self, l, f):
        a = self.get_anaph("GO_ON")
        if is_nil(a):
            a = self.get_story()
        if truthy(a) and truthy(f):
            self.andthen(["IN", self.getprop("GO_ON", "UNIT")])
        return a

    def elab(self, l, f):
        a = self.get_anaph("ELAB")
        if is_nil(a):
            a = self.get_story()
        if is_nil(a) and truthy(f):
            a = self.go_on(l, NIL)
        if truthy(a) and truthy(f):
            self.andthen(["IN", self.getprop("ELAB", "UNIT")])
        return a

    def genl(self, l, f, anaph):
        a = self.get_anaph(anaph)
        if is_nil(a):
            a = self.go_on(l, NIL)
        return a

    def who(self, l, f):
        a = self.get_anaph("WHO")
        if lambdaname(a):
            return a
        a = self.go_on(l, NIL)
        return a

    def what(self, l, f):
        a = self.get_anaph("WHAT")
        if truthy(l) and equal(cadr(self.getprop(a, "BONDVALUE")), car(l)):
            pass
        else:
            a = NIL
        if is_nil(a):
            a = self.go_on(l, T)
        return a

    def get_story(self):
        """GET_STORY: the next line of the story of the current input's
        topic (else the previous output's); flare sets continue via FLSTMT."""
        c = NIL
        for source in (self.REACTTO, self.LAST_OUTPUT):
            b = self.carn(self.getprop(source, "TOPIC"))
            if truthy(b):
                if truthy(self.getprop(b, "WORDS")):
                    c = b
                else:
                    b = self.carn(self.synnym(b))
                    if truthy(b):
                        b = self.getprop(b, "SET")
                        if truthy(b):
                            c = b
            if truthy(c):
                break
        if is_nil(c):
            return NIL
        b = self.getprop(c, "STORY")
        if truthy(b):
            self.deletep(c, self.carn(b), "STORY")
            return self.carn(b)
        if truthy(memq(c, self.getprop("FLARELIST", "SETS"))):
            return self.flstmt(c)
        return NIL

    def get_anaph(self, l):
        """GET_ANAPH: the current referent of anaphor ``l`` (via !ALLANAPHS)."""
        alist = self.ANAPHLIST if truthy(self.ANAPHLIST) else self.ANAPHLISTOLD
        ana = assoc(l, self.ALLANAPHS)
        b = NIL
        for j in to_list(ana):
            b = assoc(j, alist)
            if truthy(b):
                break
        if truthy(b) and truthy(cdr(b)) and atom(cdr(b)):
            return cdr(b)
        if l == "THEY":
            b = assoc(l, self.ANAPHLISTOLD)
            if truthy(b):
                return cdr(b)
        return NIL

    def repetition(self, sem, type_):
        """REPETITION: has SEM been used before as TYPE (IN/OUT)?  As written,
        it compares a list entry with the atom TYPE and stops at !LASTIN."""
        ptr = self.CLIST
        found = NIL
        while truthy(ptr) and is_nil(found):
            if (equal(car(ptr), type_) and equal(cadr(ptr), sem)
                    and ptr is self.LASTIN):
                found = T
            else:
                ptr = cdr(ptr)
        return found

    # -- SETUPSTL, READBONDS, CHANGEL ------------------------------------------------

    def setupstl(self):
        """SETUPSTL: story back-pointers (STORYNAME) and the sensitive words."""
        c = T
        a = [self.getprop(i, "WORDS") for i in to_list(self.getprop("SENSITIVELIST", "SETS"))]
        self.putprop("SENSITIVELIST", a or NIL, "WORDS")
        a = cons("DELNSET", append(self.getprop("FLARELIST", "SETS"),
                                   self.getprop("SETLIST", "SETS")))
        for i in to_list(a):
            for j in to_list(self.getprop(i, "STORY")):
                if truthy(j):
                    self.putprop(j, i, "STORYNAME")
                else:
                    c = NIL
        return ["SET", "UP", "OK"] if truthy(c) else ["SET", "UP", "BAD"]

    def readbonds(self, path):
        """READBONDS: evaluate PDATB (the IND / UNIT DEFPROPs)."""
        for form in read_file(path):
            self.lisp.eval(form)

    def changel(self, path):
        """CHANGEL: temporary ^H renumbering (pattern matcher -> memory)."""
        for form in read_file(path):
            if isinstance(form, Pair):
                self.putprop(form.car, form.cdr, "MEQV")
            elif isinstance(form, list) and len(form) == 2:
                self.putprop(car(form), cadr(form), "MEQV")
