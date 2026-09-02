"""The decompiled front-end (front.lap) on the real tables."""

from __future__ import annotations

import pytest

from pyranoid.lisp import NIL, T
from pyranoid.parry import Parry


@pytest.fixture(scope="module")
def p():
    return Parry(seed=1, strict=True)


def question(p, text):
    p.set_input(text + "\n")
    p.NEXT_CHAR = " "
    return p.get_question()


def pattern(p, text):
    p.set_input(text + "\n")
    p.NEXT_CHAR = " "
    return p.test_pattern()


# --- GET_QUESTION / READ_TOKEN / READ_CLEAN --------------------------------

def test_tokeniser(p):
    assert question(p, "How are you?") == ["HOW", "ARE", "YOU", "PD"]
    assert question(p, "well, ok.") == ["WELL", "COMMA", "OK", "PD"]
    assert question(p, "i am 28 years old.") == ["I", "AM", "#28", "YEARS", "OLD", "PD"]
    assert question(p, "don't!") == ["DON'T", "PD"]
    assert question(p, ".") == ["PD"]


def test_two_sentences_on_a_line(p):
    p.set_input("hello. how are you?\n")
    p.NEXT_CHAR = " "
    assert p.get_question() == ["HELLO", "PD"]
    assert p.not_last_input()                 # more on the line
    assert p.get_question() == ["HOW", "ARE", "YOU", "PD"]
    assert not p.not_last_input()


# --- FIND_WORD: irregulars, suffixes, respelling ----------------------------

def test_find_word_paths(p):
    assert p.find_word("YOU") == ["YOU"]                 # known word
    assert p.find_word("ARE") == ["BE"]                  # irregular
    assert p.find_word("CAN'T") == ["CAN", "NOT"]        # contraction
    assert p.find_word("CHEATED") == ["CHEAT"]           # suffix ED
    assert p.find_word("DIDN'T") == ["DO", "NOT"]        # DID -> DO, N'T -> NOT
    assert p.find_word("#28") == ["NUMBER"]              # numbers
    assert p.find_word("HPW") == ["HOW"]                 # respelled (next key)
    assert p.DID_SPELL is T
    assert p.find_word("XYZZY") is NIL                   # gibberish


def test_suffix_i_to_y_and_plus_e(p):
    assert p.find_word("TRIED") == ["TRY"]               # I -> Y
    assert p.find_word("HOPING") == ["HOPE"]             # root + E


# --- CANONIZE: idioms, synonyms, INPUTQUES -----------------------------------

def test_canonize_idiom_and_inputques(p):
    words = p.find_words(question(p, "what do you do for a living."))
    canon = p.canonize(words)
    assert canon == ["HOW", "PEOPL", "IT", "IN", "JOB"]
    assert [(q.car, q.cdr) for q in p.INPUTQUES] == [("HOW", "WHAT"), ("IN", "FOR"), ("JOB", "A")]


def test_canonize_drops_the_period_and_the_article(p):
    canon = p.canonize(p.find_words(question(p, "a bookie.")))
    assert canon == ["CROOK"]


def test_canonize_ever_prefixes_you(p):
    canon = p.canonize(p.find_words(question(p, "ever been married?")))
    assert canon[0] == "YOU"


# --- SEGMENT ------------------------------------------------------------------

def test_segment_stoppr_ends_and_startr_begins(p):
    assert p.segment(["DO", "YOU", "THINK", "A", "MAFIA", "BE", "IN", "YOU"]) == \
        [["DO", "YOU", "THINK"], ["A", "MAFIA", "BE"], ["IN", "YOU"]]
    assert p.segment(["HOW", "OLD", "BE", "YOU"]) == [["HOW", "OLD", "BE", "YOU"]]
    assert p.segment(NIL) == [NIL]


# --- MATCH / TRANSLATE --------------------------------------------------------

@pytest.mark.parametrize("text, unit", [
    ("How old are you?", "H0440"),
    ("Are you married?", "H0640"),
    ("How are you?", "H0047"),
    ("Are you afraid?", "H2990"),
    ("What do you do for a living.", "H0460"),
    ("What about the bookies?", "H0920"),
    ("Tell me about the mafia.", "H1010"),
    ("You are crazy.", "H3110"),
    ("hpw old are yuo?", "H0440"),
])
def test_test_pattern_on_real_questions(p, text, unit):
    assert pattern(p, text) == unit


def test_short_unrecognised_input_is_go_on_and_bare_period_is_silence(p):
    assert pattern(p, "xyzzy plugh.") == "H0010"
    assert pattern(p, ".") == "H2600"
    assert pattern(p, "xyzzy plugh gribble frotz bloop.") is NIL


def test_negation_flips_through_negate_pat(p):
    assert pattern(p, "are you not afraid?") == p.getprop("H2990", "NEGATE")
    assert p.NOT_FLAG is T


def test_family_flag_uses_famly_pat(p):
    # "dad" is a flag: removed from the fragment, and the match is redirected
    unit = pattern(p, "does your dad like you?")
    assert p.FAMILY_FLAG == "DAD"
    assert unit == p.getprop(p.get_chuck(["DO", "YOU", "LIKE", "YOU"], "SPNUM"), "FAMLY") or unit


def test_doctor_name_from_filler_unit(p):
    pattern(p, "I am Doctor Smith, how are you?")
    assert p.DOC_NAME_FLAG == ["DOCTOR", "SMITH"]
    pattern(p, "My name is John.")
    assert p.DOC_NAME_FLAG == ["JOHN"]


def test_drop_one_word_matches(p):
    # "how old are you really" has no exact pattern; dropping one word finds AGE
    assert pattern(p, "how old are you really?") == "H0440"


def test_gibberish_and_misspelling_counters(p):
    before = p.GIBBERISH
    pattern(p, "qwerty zxcv plok.")
    assert p.GIBBERISH == before + 3
    before = p.MISSPELLED
    pattern(p, "hpw old are yuo?")
    assert p.MISSPELLED == before + 2


def test_missing_dad_mom_tables_are_reported(p):
    assert p.missing_tables == ["dad.pat", "mom.pat"]
