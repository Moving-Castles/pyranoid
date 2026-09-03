"""PARRY's linguistic front-end, decompiled from ``front.lap``.

The front-end survives only as compiled PDP-10 LAP (the output of the
Stanford LISP 1.6 compiler on the MLISP source).  That LAP is regular enough
to read back: every routine below is a line-for-line decompilation, named as
in the original, with the stack/register bookkeeping turned back into
variables.  Numeric constants in the LAP are octal (it was loaded under
``IBASE 8``: ``43`` is ``#``, ``101``..``132`` are ``A``..``Z``).

Pipeline per input sentence (TEST_PATTERN):

    GET_QUESTION  read tokens up to a period-class character -> SSENT
    FIND_WORDS    per word: known? irregular? suffix-strip? respell? -> words
    CANONIZE      idioms and synonyms -> canonical 5-letter words, INPUTQUES
    SEGMENT       split at STARTR/STOPPR words into fragments
    TRANSLATE     MATCH each fragment against the simple patterns (exact, or
                  minus one word), drop fillers, combine with the compound
                  patterns (exact, or minus one unit) -> a ^H unit

Data tables are loaded exactly as INIT_DICTIO loads them, onto property
lists: STARTR/STOPPR/FLAGS/FILLER marks, IRREG and SYNONM values, SUFFIX and
IDIOM entries indexed by first element, NEGATE/FAMLY pairs, NEARBY keys.
The simple/compound pattern tables reproduce the binary-table semantics of
``parfns.fai`` (SPAT/CPAT look a word list up by its words' first five
characters; SYNNYM returns a five-character canonical word).

``DAD.PAT`` and ``MOM.PAT`` are not in the surviving source tree; the seven
entries of each were recovered from the property lists in the November 1974
core image (PARRY.DMP) and are bundled as ``dad.pat`` / ``mom.pat``.
"""

from __future__ import annotations

from pathlib import Path

from pyranoid.lisp import (
    NIL,
    LispError,
    T,
    append,
    assoc,
    cadr,
    car,
    cddr,
    cdr,
    cons,
    equal,
    explode,
    is_nil,
    lambdaname,
    last,
    length,
    memq,
    numberp,
    pname,
    prelist,
    read_file,
    readlist,
    reverse,
    subst,
    suflist,
    to_list,
    truthy,
)

# character atoms (the SPECIAL variables BLANK, CR, PERIOD, COMMA, ALTMODE ...)
BLANK = " "
CR = "\n"
PERIOD = "."
COMMA = ","
ALTMODE = "\x1b"

_PERIOD_CHARS = ["!", "%", ")", ".", "?", "]"]          # (! PERCENT RPAR PERIOD ? RSBR)
_COMMA_CHARS = [",", ":", ";"]                          # (COMMA COLON SEMICOLON)
_CR_CHARS = [CR, ALTMODE]
_STOP_CHARS = [CR, BLANK, COMMA, PERIOD]

_NAME_LEAD = ["I'M", "AM", "NAME", "CALL", "ME"]
_NAME_FOLLOW = ["DR", "DOCTOR", "CALLED", "IS", "ME", "AS"]
_DR = ["DR", "DOCTOR"]
_FAMILY = ["DAD", "MOM", "FAMLY"]
_DISBELIEF_FILLERS = ["H3150", "P5245"]


def _trunc5(w) -> str:
    return pname(w)[:5]


class FrontMixin:
    """The pattern front-end (front.lap), as a mixin on the PARRY image."""

    # -- PMINITIALIZE / INIT_CHAR / INIT_DICTIO --------------------------------

    def pminitialize(self, data_dir: Path) -> None:
        """PMINITIALIZE with the production answers (USE_CHUCK, USE_BILL, no
        disk input, no learning mode)."""
        self.USE_CHUCK = T
        self.init_char()
        self.init_dictio(data_dir)
        self.USE_BILL = T
        # OPEN_DISK with no disk input file:
        self.STOP_ON = "H0045"
        self.LEARNING = NIL
        self.WINDOWS = NIL
        self.NEXT_CHAR = BLANK

    def init_char(self) -> None:
        for c in _PERIOD_CHARS:
            self.putprop(c, T, "PERIOD")
        for c in _COMMA_CHARS:
            self.putprop(c, T, "COMMA")
        for c in _CR_CHARS:
            self.putprop(c, T, "CR")
        for c in _STOP_CHARS:
            self.putprop(c, T, "STOP")
        self.DO_SPELL = T
        self.DID_SPELL = NIL
        self.GIBBERISH = 0
        self.MISSPELLED = 0

    def init_dictio(self, d: Path) -> None:
        self.equate(d / "nearby.key", "NEARBY", T)      # (done in INIT_CHAR originally)
        self.mark(d / "startr.alf", "STARTR")
        self.mark(d / "stoppr.alf", "STOPPR")
        self.mark(d / "flags.alf", "FLAGS")
        self.set_val(d / "irreg.alf", "IRREG")
        self.store_idiom(d / "suffix.alf", "SUFFIX")
        self.store_idiom(d / "idiom.alf", "IDIOM")
        # With USE_CHUCK the originals came from the SETUP-built binary
        # tables (ALL.PAR), whose ultimate source is these three files.
        self.set_val(d / "synonm.alf", "SYNONM")
        self.SPTABLE: dict = {}
        self.CPTABLE: dict = {}
        self.store_pat(d / "spats.sel", "SPATS", self.SPTABLE)
        self.store_pat(d / "cpats.sel", "CPATS", self.CPTABLE)
        self.mark(d / "filler.pat", "FILLER")
        self.equate(d / "negate.pat", "NEGATE", NIL)
        self.missing_tables: list[str] = []
        for name in _FAMILY:
            path = d / f"{name.lower()}.pat"
            if path.exists():
                self.equate(path, name, NIL)
            else:
                self.missing_tables.append(path.name)

    # -- the table loaders (MARK, SET_VAL, EQUATE, STORE_IDIOM, STORE_PAT) -----

    def mark(self, path: Path, prop: str) -> None:
        """MARK: each form X in the file gets (PUTPROP X T prop)."""
        for x in read_file(path):
            self.putprop(x, T, prop)

    def set_val(self, path: Path, prop: str) -> None:
        """SET_VAL: (WORD VALUE...) -> (PUTPROP WORD (VALUE...) prop)."""
        for x in read_file(path):
            if isinstance(x, list):
                self.putprop(car(x), cdr(x), prop)

    def equate(self, path: Path, prop: str, both_ways) -> None:
        """EQUATE: (A B) -> (PUTPROP A B prop), and (PUTPROP B A prop) if flagged."""
        for x in read_file(path):
            if not isinstance(x, list):
                continue
            self.putprop(car(x), cadr(x), prop)
            if truthy(both_ways):
                self.putprop(cadr(x), car(x), prop)

    def store_idiom(self, path: Path, prop: str) -> None:
        """STORE_IDIOM: index an idiom/suffix table by its first element.

        Each entry becomes (REST LENGTH-OF-REST . REPLACEMENT) on the first
        element's ``prop`` list (newest first).  For SUFFIX the key is the
        exploded suffix reversed, so lookup runs from a word's last letter.
        """
        for x in read_file(path):
            if not isinstance(x, list):
                continue
            if prop == "IDIOM":
                key_list = car(x)
                repl = cdr(x)
            else:
                key_list = reverse(explode(car(x)))
                repl = cdr(x)
            rest = cdr(key_list)
            entry = cons(rest, cons(length(rest), repl))
            self.addprop(car(key_list), entry, prop)

    def store_pat(self, path: Path, prop: str, table: dict) -> None:
        """STORE_PAT: ((WORDS...) NAME) -> table[words] = NAME, and NAME's
        ``prop`` list collects its patterns (the STHGHT reverse index)."""
        for x in read_file(path):
            if not isinstance(x, list):
                continue
            pat, name = car(x), cadr(x)
            table[self.at(pat)] = name
            self.addprop(name, pat, prop)

    def addprop(self, atom_, value, prop) -> None:
        """ADDPROP: push ``value`` onto the front of ``atom_``'s ``prop`` list."""
        self.putprop(atom_, cons(value, self.getprop(atom_, prop)), prop)

    @staticmethod
    def at(word_list) -> tuple:
        """The table key for a word list: the words' first five characters
        (SCPAT in parfns.fai stores one 36-bit word = 5 characters per word)."""
        return tuple(_trunc5(w) for w in to_list(word_list))

    # -- GET_CHUCK: the table interface ----------------------------------------

    def synnym(self, word):
        """SYNNYM (parfns.fai): exact lookup of a word, value a 5-letter word."""
        if isinstance(word, (list, tuple)) or is_nil(word):
            return NIL
        return self.getprop(word, "SYNONM")

    def spat(self, word_list):
        return self.SPTABLE.get(self.at(word_list))

    def cpat(self, unit_list):
        return self.CPTABLE.get(self.at(unit_list))

    def get_chuck(self, x, kind):
        if kind == "SYNONM":
            if truthy(self.USE_CHUCK):
                self.window(12, T, x)
                r = self.synnym(x)
                if truthy(r):
                    return r
            return self.getprop(x, "SYNONM")
        if kind == "IRREG":
            self.window(12, T, x)
            return self.getprop(x, "IRREG")
        if kind == "SPELL":
            w = readlist(x)
            if truthy(self.get_chuck(w, "SYNONM")):
                return [w]
            return self.get_chuck(w, "IRREG")
        if kind == "SPNUM":
            self.window(17, T, x)
            r = self.spat(x)
            if truthy(r):
                self.SP_MATCH = cons(x, self.SP_MATCH)
            return r
        if kind == "CPNUM":
            self.window(17, T, x)
            r = self.cpat(x)
            if truthy(r):
                self.CP_MATCH = x
            return r
        if kind == "SPATS":
            return self.getprop(x, "SPATS")
        if kind == "CPATS":
            return self.getprop(x, "CPATS")
        raise LispError("Invalid call on GET_CHUCK")

    # -- input: GET_QUESTION / READ_TOKEN / READ_CLEAN / GET_SAFE --------------

    def set_input(self, text: str) -> None:
        """Make ``text`` the terminal input stream (READCH reads from it)."""
        self._chars = list(text)
        self._pos = 0

    def readch(self):
        """READCH: the next character; digits read as numbers; CR at end."""
        if self._pos >= len(self._chars):
            self._pos += 1
            if self._pos > len(self._chars) + 2:
                raise LispError("input exhausted")
            return CR
        c = self._chars[self._pos]
        self._pos += 1
        return int(c) if c.isdigit() else c

    def read_clean(self):
        c = self.readch()
        if numberp(c):
            return c
        code = ord(c)
        if 65 <= code <= 90 or code == 39:            # A..Z or '
            return c
        if 97 <= code <= 122:                          # a..z -> upper case
            return chr(code - 32)
        if truthy(self.getprop(c, "COMMA")):
            return COMMA
        if truthy(self.getprop(c, "PERIOD")):
            return PERIOD
        if truthy(self.getprop(c, "CR")):
            return CR
        if code == 8 and truthy(self.LEARNING):
            return c
        return BLANK

    def get_safe(self, x, prop):
        return NIL if numberp(x) else self.getprop(x, prop)

    def read_token(self):
        while self.NEXT_CHAR in (BLANK, CR):
            self.NEXT_CHAR = self.read_clean()
        token: list = []                                  # kept reversed, as the original
        if numberp(self.NEXT_CHAR):
            token = ["#"]
        while is_nil(self.get_safe(self.NEXT_CHAR, "STOP")):
            token = cons(self.NEXT_CHAR, token)
            self.NEXT_CHAR = self.read_clean()
        if token:
            return readlist(reverse(token))
        c = self.NEXT_CHAR
        if c == COMMA:
            self.NEXT_CHAR = self.read_clean()
            return c
        while truthy(self.get_safe(self.NEXT_CHAR, "STOP")) and self.NEXT_CHAR != CR:
            self.NEXT_CHAR = self.read_clean()
        return c

    def get_question(self):
        """GET_QUESTION: the tokens of one sentence, COMMA atoms for commas,
        ending in PD."""
        out: list = []
        while True:
            t = self.read_token()
            if t == PERIOD:
                out.append("PD")
                return out
            out.append("COMMA" if t == COMMA else t)

    def not_last_input(self) -> bool:
        """NOT_LAST_INPUT (pmem4): more input remains on the line."""
        return self.NEXT_CHAR != CR

    # -- FIND_WORDS / FIND_WORD / DE_SUFFIX / ROOT_VAL / RE_SPELL --------------

    def find_words(self, sent):
        result = NIL
        for word in to_list(sent):
            self.window(11, T, word)
            r = self.find_word(word)
            self.window(3, NIL, r)
            if is_nil(r):
                self.GIBBERISH += 1
            elif truthy(self.DID_SPELL):
                self.MISSPELLED += 1
                self.DID_SPELL = NIL
            result = append(result, r)
        return result

    def find_word(self, word):
        if truthy(self.get_chuck(word, "SYNONM")):
            return [word]
        r = self.get_chuck(word, "IRREG")
        if truthy(r):
            return r
        r = self.de_suffix(word)
        if truthy(r):
            return r
        r = self.re_spell(word)
        if truthy(r):
            return r
        if self.LEARNING == "SYNONM":
            r = self.learn(word)
        return r

    def de_suffix(self, word):
        chars = explode(word)
        result = NIL
        if pname(car(chars))[:1] == "#":
            result = ["NUMBER"]
        else:
            n = length(chars)
            if not (n <= 3 or n >= 20):
                rev = reverse(chars)
                s = self.getprop(car(rev), "SUFFIX")
                result = s
                if truthy(s):
                    result = self.root_val(cdr(rev), s)
        self.DID_SPELL = NIL
        if truthy(result) and self.LEARNING == "SYNONM" and is_nil(self.getprop(word, "SUF")):
            if truthy(self.get_inp(f"Is {pname(word)} like {result}")):
                self.putprop(word, T, "SUF")
            else:
                result = NIL
        return result

    def root_val(self, rev, suffixes):
        """ROOT_VAL: try each suffix entry against the reversed letters; on a
        hit look the root up (as I->Y, +E, or bare) and append the
        replacement words."""
        for entry in to_list(suffixes):
            e_chars, n = car(entry), cadr(entry)
            if not equal(prelist(rev, n), e_chars):
                continue
            root_rev = suflist(rev, n)
            if is_nil(root_rev):
                return NIL
            result = NIL
            if car(root_rev) == "I":
                result = self.find_word(readlist(reverse(cons("Y", cdr(root_rev)))))
            if is_nil(result):
                result = self.find_word(readlist(reverse(cons("E", root_rev))))
            if is_nil(result):
                result = self.find_word(readlist(reverse(root_rev)))
            if is_nil(result):
                return NIL
            return append(result, cddr(entry))
        return NIL

    def re_spell(self, word):
        if is_nil(self.DO_SPELL):
            return NIL
        chars = explode(word)
        result = NIL
        if not (length(chars) >= 15 or is_nil(cdr(chars)) or numberp(cadr(chars))):
            result = self.drop_one_rev(NIL, reverse(chars), "SPELL")
            if is_nil(result):
                result = self.next_key(NIL, chars)
            if is_nil(result):
                result = self.transpose(NIL, chars)
            if truthy(result):
                self.DID_SPELL = T
        if truthy(result) and self.LEARNING == "SYNONM" and is_nil(self.getprop(word, "RES")):
            if truthy(self.get_inp(f"Does {pname(word)} spell {result}")):
                self.putprop(word, T, "RES")
            else:
                result = NIL
        return result

    def drop_one_rev(self, pre, rest, kind):
        """DROP_ONE_REV: delete one letter at a time (from the end) and look up."""
        while truthy(rest):
            r = self.get_chuck(append(reverse(cdr(rest)), pre), kind)
            if truthy(r):
                return r
            pre = cons(car(rest), pre)
            rest = cdr(rest)
        return NIL

    def next_key(self, pre, rest):
        """NEXT_KEY: replace one letter by its keyboard neighbour and look up."""
        while truthy(rest):
            n = self.get_safe(car(rest), "NEARBY")
            if truthy(n):
                r = self.get_chuck(append(pre, cons(n, cdr(rest))), "SPELL")
                if truthy(r):
                    return r
            pre = append(pre, [car(rest)])
            rest = cdr(rest)
        return NIL

    def transpose(self, pre, rest):
        """TRANSPOSE: swap adjacent letters and look up."""
        while truthy(cdr(rest)):
            swapped = cons(cadr(rest), cons(car(rest), cddr(rest)))
            r = self.get_chuck(append(pre, swapped), "SPELL")
            if truthy(r):
                return r
            pre = append(pre, [car(rest)])
            rest = cdr(rest)
        return NIL

    def learn(self, word):
        """LEARN: the interactive synonym-teaching mode (LEARNING = SYNONM).
        Answers come from the GET_INP hook; with no teacher it declines."""
        if truthy(self.getprop(word, "LEA")):
            return NIL
        ans = self.get_inp(f"What is {pname(word)}")
        if is_nil(ans):
            self.putprop(word, T, "LEA")
            return NIL
        if not isinstance(ans, list):
            while is_nil(self.get_chuck(ans, "SYNONM")):
                ans = self.get_inp(f"Try again {pname(word)}")
                if is_nil(ans):
                    self.putprop(word, T, "LEA")
                    return NIL
            self.putprop(word, ans, "SYNONM")
            self.learned.append(cons(word, ans))
        else:
            rest = cdr(car(ans))
            self.addprop(car(car(ans)), cons(rest, cons(length(rest), cdr(ans))), "IDIOM")
            self.learned.append(ans)
            self.putprop(car(car(ans)), ["A"], "SYNONM")
        return [word]

    def get_inp(self, prompt: str):
        """GET_INP: a yes/no or value prompt to the operator.  The port has no
        operator; ``N`` (NIL) is the answer, which disables learning."""
        hook = getattr(self, "operator", None)
        if hook is None:
            return NIL
        ans = hook(prompt)
        return NIL if ans in (None, "N", "n") else ans

    # -- CANONIZE / IDIOM_VAL / SAME --------------------------------------------

    def canonize(self, words):
        self.INPUTQUES = NIL
        result = NIL
        if truthy(memq(car(words), ["EVER", "ANY"])):
            result = ["YOU"]
        rest = words
        while truthy(rest):
            w = car(rest)
            self.window(13, T, w)
            rest = cdr(rest)
            self.ANY = NIL
            idioms = self.getprop(w, "IDIOM")
            v = NIL
            if truthy(idioms):
                v = self.idiom_val(idioms, rest)
            if truthy(v):
                self.window(14, T, cons(w, car(v)))
                rest = suflist(rest, cadr(v))
                v = cddr(v)
                if truthy(self.ANY):
                    v = subst(car(self.get_chuck(self.ANY, "SYNONM")), "any", v)
            else:
                v = self.get_chuck(w, "SYNONM")
            if truthy(v) and not equal(v, ["A"]):
                self.window(4, NIL, car(v))
                result = append(result, v)
                self.INPUTQUES = cons(cons(car(v), w), self.INPUTQUES)
        self.INPUTQUES = reverse(self.INPUTQUES)
        return result

    def idiom_val(self, idioms, rest):
        for e in to_list(idioms):
            if truthy(self.same(car(e), prelist(rest, cadr(e)))):
                return e
        return NIL

    def same(self, pat, ws):
        if equal(pat, ws):
            return T
        if is_nil(ws):
            return NIL
        if car(ws) == car(pat):
            return self.same(cdr(pat), cdr(ws))
        if car(pat) == "any":
            self.ANY = car(ws)
            if truthy(self.ANY):
                return self.same(cdr(pat), cdr(ws))
        return NIL

    # -- SEGMENT ------------------------------------------------------------------

    def segment(self, words):
        return self.segment1(NIL, words)

    def segment1(self, a, b):
        """SEGMENT1: a STOPPR word ends the current fragment (and stays in it);
        a STARTR word begins a new one."""
        if is_nil(b):
            return [a]
        w = car(b)
        if truthy(self.getprop(w, "STOPPR")):
            if truthy(cdr(b)):
                return cons(append(a, [w]), self.segment(cdr(b)))
            return [append(a, [w])]
        if truthy(self.getprop(w, "STARTR")):
            if truthy(a):
                return cons(a, self.segment(b))
            return self.segment1([w], cdr(b))
        return self.segment1(append(a, [w]), cdr(b))

    # -- TRANSLATE / MATCH / DE_FLAG / ANAPH_REF / DROP_ONE / DE_FILL -----------

    def translate(self, pattern):
        matches = NIL
        for f in to_list(pattern):
            self.window(16, T, f)
            matches = append(matches, self.match(f))
        self.DOC_NAME_FLAG = NIL
        units = self.de_fill(matches)
        result = NIL
        if truthy(units):
            if is_nil(cdr(units)):
                result = self.first_lambda(units)
            else:
                result = self.get_chuck(units, "CPNUM")
                if is_nil(result):
                    if is_nil(cddr(units)):
                        result = self.first_lambda(reverse(units))
                    else:
                        result = self.drop_one(NIL, units, "CPNUM")
                        if is_nil(result):
                            result = self.first_lambda(reverse(units))
        if is_nil(result):
            result = self.first_lambda(reverse(matches))
        return result

    def match(self, fragment):
        self.FAMILY_FLAG = NIL
        self.NOT_FLAG = NIL
        ws = self.de_flag(fragment)
        r = NIL
        if truthy(ws):
            r = self.get_chuck(ws, "SPNUM")
            if is_nil(r):
                r = self.drop_one(NIL, ws, "SPNUM")
        if truthy(self.NOT_FLAG):
            n = self.getprop(r, "NEGATE")
            if truthy(n):
                r = n
        if truthy(self.FAMILY_FLAG):
            f = self.getprop(r, self.FAMILY_FLAG)
            if is_nil(f):
                f = self.getprop(r, "FAMLY")
            if truthy(f):
                r = f
        return [r] if truthy(r) else NIL

    def de_flag(self, ws):
        """DE_FLAG: strip the flag words, noting negation and family
        references, and resolving THEY to its anaphoric referent."""
        out: list = []
        rest = ws
        while truthy(rest):
            w = car(rest)
            rest = cdr(rest)
            if is_nil(self.getprop(w, "FLAGS")):
                out.append(w)
            elif w == "THEY":
                w2 = car(self.anaph_ref(w))
                if truthy(memq(w2, _FAMILY)):
                    out.append("YOU")
                rest = cons(w2, rest)
            elif w == "NOT":
                self.NOT_FLAG = NIL if truthy(self.NOT_FLAG) else T
            elif truthy(memq(w, _FAMILY)):
                self.FAMILY_FLAG = w
        return out or NIL

    def anaph_ref(self, word):
        r = self.get_anaph(word) if truthy(self.USE_BILL) else self.get_inp(f"Anaphoric reference for {word}")
        if is_nil(r):
            r = "PEOPLE"
        pair = assoc(word, self.INPUTQUES)
        self.window(15, T, cdr(pair) if truthy(pair) else NIL)
        self.window(15, NIL, r)
        s = self.get_chuck(car(self.find_word(r)), "SYNONM")
        return s if truthy(s) else ["PEOPL"]

    def drop_one(self, pre, rest, kind):
        """DROP_ONE: look the list up with one element deleted, left to right."""
        while truthy(rest):
            r = self.get_chuck(append(pre, cdr(rest)), kind)
            if truthy(r):
                return r
            pre = append(pre, [car(rest)])
            rest = cdr(rest)
        return NIL

    def de_fill(self, units):
        """DE_FILL: drop filler units; a disbelief filler negates the unit that
        follows it; the "I am Dr X" filler captures the doctor's name."""
        out: list = []
        rest = units
        while truthy(rest):
            u = car(rest)
            rest = cdr(rest)
            if is_nil(self.getprop(u, "FILLER")):
                out.append(u)
            elif truthy(memq(u, _DISBELIEF_FILLERS)):
                nxt = car(rest)
                if truthy(rest) and truthy(self.getprop(nxt, "NEGATE")) and nxt != "P0000":
                    rest = cons(self.getprop(nxt, "NEGATE"), cdr(rest))
            elif u == "H0630":
                self.get_name()
        return out or NIL

    def get_name(self):
        """GET_NAME: find "I am Dr X" / "my name is X" in SSENT -> DOC_NAME_FLAG."""
        s = self.SSENT
        while True:
            w = car(s)
            s = cdr(s)
            if is_nil(s):
                break
            if truthy(memq(w, _NAME_LEAD)) and truthy(memq(car(s), _NAME_FOLLOW)):
                break
        if truthy(s):
            if truthy(memq(car(s), _DR)):
                s = ["DOCTOR", cadr(s)]
            else:
                s = cdr(s)
                if truthy(memq(car(s), _DR)):
                    s = ["DOCTOR", cadr(s)]
                else:
                    s = [car(s)]
        if truthy(s) and car(last(s)) != "PD":
            self.DOC_NAME_FLAG = s
        else:
            self.DOC_NAME_FLAG = T
        return NIL

    @staticmethod
    def first_lambda(units):
        for u in to_list(units):
            if lambdaname(u):
                return u
        return NIL

    # -- TEST_PATTERN -----------------------------------------------------------------

    def test_pattern(self):
        """TEST_PATTERN: read one sentence and return its ^H unit (or NIL)."""
        self.SSENT = self.get_question()
        self.window(1, T, "INPUT")
        self.window(2, T, self.SSENT)
        if truthy(self.LEARNING):
            self.RIGHT = car(self.SSENT)
            self.SSENT = cdr(self.SSENT)
        self.window(1, T, "RESPELLED")
        ws = self.find_words(self.SSENT)
        self.window(3, T, ws)
        if self.LEARNING == "SYNONM":
            return self.RIGHT
        self.window(1, T, "CANONIZE")
        canon = self.canonize(ws)
        self.window(4, T, canon)
        self.window(1, T, "SEGMENT")
        self.PATTERN = self.segment(canon)
        self.window(5, T, self.PATTERN)
        self.CP_MATCH = NIL
        self.SP_MATCH = NIL
        self.window(1, T, "MATCH")
        result = self.translate(self.PATTERN)
        self.window(7, T, reverse(self.SP_MATCH))
        self.window(8, T, self.CP_MATCH)
        if is_nil(result) and length(self.SSENT) <= 4:
            result = "H0010" if truthy(cdr(self.SSENT)) else "H2600"
        self.window(9, T, result)
        return result
