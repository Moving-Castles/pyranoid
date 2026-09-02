"""Tests for the front-end matcher against real interview questions."""

from __future__ import annotations

import pytest

from pyranoid.data import DATA_DIR, Lexicon
from pyranoid.frontend import FrontEnd
from pyranoid.pdat import load_pdat

SRC = DATA_DIR
PDATZ = DATA_DIR / "pdatz.txt"


@pytest.fixture(scope="module")
def fe():
    if not (SRC / "dictio").exists():
        pytest.skip("original source missing")
    return FrontEnd(Lexicon.load(SRC))


@pytest.fixture(scope="module")
def mem():
    if not PDATZ.exists():
        pytest.skip("recovered pdat missing")
    return load_pdat(PDATZ)


def _reply(fe, mem, q):
    a = fe.analyse(q)
    if a.unit and a.unit in mem.beliefs:
        e = mem.response_for(a.unit)
        if e and e.normal:
            return a.unit, {r.words for r in e.normal}
    return a.unit, set()


def test_subsequence_matcher():
    assert FrontEnd._is_subsequence(("A", "C"), ["A", "B", "C"]) is True
    assert FrontEnd._is_subsequence(("C", "A"), ["A", "B", "C"]) is False


def test_canonicalisation_expands_and_maps(fe):
    # synonym maps ARE -> BE; a contraction expands and its parts canonicalise
    assert "BE" in fe.canonise("are you")          # ARE -> BE
    # CAN'T -> CAN NOT, then CAN -> COULD via the synonym table
    out = fe.canonise("can't")
    assert len(out) == 2 and out[-1] == "NOT"


@pytest.mark.parametrize("question, expect_unit, expect_text", [
    ("How old are you?", "H0440", "TWENTY-EIGHT, HOW OLD ARE YOU?"),
    ("Are you married?", "H0640", "I'M NOT MARRIED"),
    ("How are you?", "H0047", None),
    ("Are you afraid?", "H2990", "I'M AFRAID OF YOU"),
])
def test_real_questions_map_to_real_responses(fe, mem, question, expect_unit, expect_text):
    unit, texts = _reply(fe, mem, question)
    assert unit == expect_unit
    if expect_text is not None:
        assert expect_text in texts


def test_mafia_is_not_a_spats_match(fe):
    # the Mafia is handled by the paranoid model, not the pattern table
    a = fe.analyse("do you know the mafia")
    assert a.unit is None


def test_coverage_is_reasonable(fe, mem):
    # a decent share of spat targets resolve to real responses (data has gaps)
    hit = 0
    total = 0
    for sp in fe.lex.spats:
        if sp.target.startswith("H"):
            total += 1
            b = mem.beliefs.get(sp.target)
            if b and b.resp in mem.responses:
                hit += 1
    assert hit / total > 0.7
