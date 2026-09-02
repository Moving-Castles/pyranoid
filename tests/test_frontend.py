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


def test_negation_flips_unit(fe, mem):
    # "are you afraid" -> afraid unit; "are you not afraid" -> its negation
    pos = fe.analyse("are you afraid").unit
    neg = fe.analyse("are you not afraid").unit
    assert pos and neg and pos != neg
    assert pos in fe.negate_map and fe.negate_map[pos] == neg


def test_suffix_stripping_reaches_root(fe):
    # an inflected form reduces toward a recognised root
    assert "CHEAT" in fe.canonise("were you cheated")


def test_fragment_segmentation(fe):
    # a stoppr verb (THINK) drops the framing clause; startr (WHY) begins a fragment
    frags = fe.segment(["DO", "YOU", "THINK", "A", "MAFIA", "BE", "IN", "YOU"])
    assert ["DO", "YOU"] not in frags          # framing clause dropped
    assert any("MAFIA" in f for f in frags)


def test_work_question_matches_job(fe, mem):
    # regression the fragmenter fixed: "for a living" reaches the work unit
    a = fe.analyse("what do you do for a living")
    assert a.unit in mem.beliefs
    e = mem.response_for(a.unit)
    assert e and any("SEARS" in r.words or "WORK" in r.words for r in e.normal)
