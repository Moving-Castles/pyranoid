"""The LISP substrate: reader, list primitives, property lists, evaluator."""

from __future__ import annotations

import pytest

from pyranoid.lisp import (
    NIL,
    Lisp,
    LispError,
    Pair,
    Plist,
    Reader,
    T,
    append,
    assoc,
    car,
    cdr,
    cons,
    delete,
    deleten,
    explode,
    memq,
    normalise_glyphs,
    prelist,
    read_forms,
    readlist,
    suflist,
)


def read1(text):
    return Reader(normalise_glyphs(text)).read()


# --- reader -----------------------------------------------------------------

def test_atoms_lists_numbers():
    assert read1("HELLO") == "HELLO"
    assert read1("(A B C)") == ["A", "B", "C"]
    assert read1("(A (B C) D)") == ["A", ["B", "C"], "D"]
    assert read1("(SETQ AJUMP 0.2)") == ["SETQ", "AJUMP", 0.2]
    assert read1("(X -100 100)") == ["X", -100, 100]


def test_nil_and_t():
    assert read1("NIL") is NIL
    assert read1("()") is NIL
    assert read1("T") is T
    assert read1("(EXH T)") == ["EXH", True]


def test_dotted_pairs():
    r = read1("(WHY . H0300)")
    assert isinstance(r, Pair) and r.car == "WHY" and r.cdr == "H0300"
    r = read1("(THEY.MAFIA)")
    assert isinstance(r, Pair) and r.car == "THEY" and r.cdr == "MAFIA"
    r = read1("((WHY . λ0300)(WHO . λ0160))")
    assert [p.cdr for p in r] == ["H0300", "H0160"]


def test_quote_macro_and_super_parens():
    assert read1("@GAMES") == ["QUOTE", "GAMES"]
    assert read1("@ (MAFIA STRONGFEELINGS)") == ["QUOTE", ["MAFIA", "STRONGFEELINGS"]]
    assert read1("[COND ((GREATERP INPUTNO 3) @λ0010) (T NIL) ]") == \
        ["COND", [["GREATERP", "INPUTNO", 3], ["QUOTE", "H0010"]], [True, None]]


def test_comments_and_escapes():
    forms = list(read_forms("(A B) ~ a comment (not read)\n(C D)"))
    assert forms == [["A", "B"], ["C", "D"]]
    assert read1("(GANGSTERS/. THEY)") == ["GANGSTERS.", "THEY"]
    assert read1("(OK/, THIS)") == ["OK,", "THIS"]


def test_glyphs():
    assert read1("(#B λ0050 100 (LOCATION I HOSPITAL))")[1] == "H0050"
    assert read1("(RESP α0080)")[1] == "B0080"


def test_stray_closers_at_top_level_are_ignored():
    assert list(read_forms("(PRINT @(INITIALIZE OK))  ]]]]]")) == [["PRINT", ["QUOTE", ["INITIALIZE", "OK"]]]]


# --- list primitives ------------------------------------------------------

def test_car_cdr_cons():
    assert car(NIL) is NIL and cdr(NIL) is NIL
    assert car(["A"]) == "A" and cdr(["A"]) is NIL
    assert cons("A", NIL) == ["A"]
    assert cons("A", ["B"]) == ["A", "B"]
    assert isinstance(cons("A", "B"), Pair)
    assert append(NIL, ["X"]) == ["X"] and append(["X"], NIL) == ["X"]


def test_assoc_memq_prelist_suflist_delete():
    al = [Pair("WHY", "H0300"), ["WHO", "H0160"]]
    assert assoc("WHY", al).cdr == "H0300"
    assert assoc("WHO", al) == ["WHO", "H0160"]
    assert assoc("NOPE", al) is NIL
    assert memq("B", ["A", "B", "C"]) == ["B", "C"]
    assert prelist(["A", "B", "C"], 2) == ["A", "B"] and prelist(["A"], 0) is NIL
    assert suflist(["A", "B", "C"], 2) == ["C"] and suflist(["A"], 1) is NIL
    assert deleten(["A", "B", "C"], 2) == ["A", "C"]
    assert delete("B", ["A", "B", "B"]) == ["A", "B"]


def test_explode_readlist():
    assert explode("#28") == ["#", 2, 8]
    assert readlist(["H", "O", "W"]) == "HOW"
    assert readlist(explode("#28")) == "#28"


# --- property lists and the evaluator ---------------------------------------

class Host:
    """A stand-in for the PARRY image: variables as attributes, one function."""

    def __init__(self):
        self.AJUMP = NIL
        self.MISTRUST = 12
        self.INPUTNO = 5
        self.calls = []
        self.printed = []

    def lisp_get(self, name):
        try:
            return getattr(self, name)
        except AttributeError:
            raise LispError(name) from None

    def lisp_set(self, name, value):
        setattr(self, name, value)

    def lisp_fn(self, name):
        if name == "CHOOSE":
            return lambda g: self.calls.append(g) or "H2613"
        return None

    def lisp_print(self, x):
        self.printed.append(x)


@pytest.fixture
def lisp():
    host = Host()
    return Lisp(host, Plist()), host


def test_prog2_returns_second_value_and_evaluates_all(lisp):
    lp, host = lisp
    form = read1("[PROG2 (SETQ AJUMP 0.2) (CHOOSE (QUOTE GUARD)) (SETQ WDFLAG (QUOTE SENSITIVELIST))]")
    assert lp.eval(form) == "H2613"
    assert host.AJUMP == 0.2 and host.WDFLAG == "SENSITIVELIST" and host.calls == ["GUARD"]


def test_cond_and_arithmetic(lisp):
    lp, host = lisp
    assert lp.eval(read1("[COND ((GREATERP MISTRUST 10) @H4070) ((GREATERP MISTRUST 5) @H4080) (T @H4090)]")) == "H4070"
    assert lp.eval(read1("[COND ((GREATERP INPUTNO 3) @H0010) (T NIL)]")) == "H0010"
    host.INPUTNO = 2
    assert lp.eval(read1("[COND ((GREATERP INPUTNO 3) @H0010) (T NIL)]")) is NIL
    assert lp.eval(read1("(DIFFERENCE MISTRUST 1)")) == 11
    assert lp.eval(read1("(*QUO (TIMES 30 7) 4)")) == 52


def test_prog_return_and_memq(lisp):
    lp, host = lisp
    host.TOPIC = ["BOOKIESET"]
    form = read1("[PROG (A) (SETQ A (CARN TOPIC)) (RETURN (COND ((MEMQ A (QUOTE (RELATIONS BOOKIESET))) (QUOTE H1775)) (T NIL)))]")
    assert lp.eval(form) == "H1775"


def test_defprop_get_mapcar_lambda(lisp):
    lp, host = lisp
    for form in read_forms("""
        (SETQ FL @((RACKETSET (RACKETEERS CRIME) WORDS) (MAFIASET (MAFIA) WORDS)))
        (MAPCAR (FUNCTION (LAMBDA (X) (EVAL (CONS @DEFPROP X)))) FL)
        (SETQ WTS @(17 15))
        (SETQ SETS @(RACKETSET MAFIASET))
        (MAPCAR (FUNCTION (LAMBDA (WT) (PROG2 (PUTPROP (CAR SETS) WT @WT) (SETQ SETS (CDR SETS))))) WTS)
    """):
        lp.eval(form)
    assert lp.plist.get("RACKETSET", "WORDS") == ["RACKETEERS", "CRIME"]
    assert lp.plist.get("RACKETSET", "WT") == 17 and lp.plist.get("MAFIASET", "WT") == 15
    assert host.SETS is NIL


def test_unbound_variable_is_an_error(lisp):
    lp, _ = lisp
    with pytest.raises(LispError):
        lp.eval("NOSUCHVAR")


def test_putprop_on_a_list_is_inert():
    pl = Plist()
    pl.put(["MEASURE", "FEAR", 14], "X", "TH2")
    assert pl.get(["MEASURE", "FEAR", 14], "TH2") is NIL
    pl.put(NIL, "H4804", "FAMLY")
    assert pl.get(NIL, "FAMLY") == "H4804"
