"""Tests for the belief/inference engine and its integration into REACT."""

from __future__ import annotations

import pytest

from pyranoid.beliefs import BeliefBase
from pyranoid.inference import Inference
from pyranoid.model import Model
from pyranoid.parry import Parry


@pytest.fixture(scope="module")
def bb():
    return BeliefBase.load()


def _infer(bb, unit, version="STRONG"):
    m = Model(version)
    m.fjump = m.ajump = m.hjump = None
    inf = Inference(bb, m)
    inf.infer(unit, {"FEAR": 5, "ANGER": 5, "MISTRUST": 5, "INPUTNO": 1})
    return inf, m


def test_insult_unit_asserts_doctor_beliefs(bb):
    # H3110 carries TH2=DBABNORMAL; H3000 carries DINSULTS/DHOSTILE
    inf, m = _infer(bb, "H3110")
    assert "DBABNORMAL" in inf.truth
    # asserting DBABNORMAL fires HJUMP/FJUMP/AJUMP (the EMOTE rule)
    assert m.hjump and m.hjump >= 0.3


def test_bl_thresholds(bb):
    inf, _ = _infer(bb, None)
    # an intention with score >= 5 is BL-true; PINTERACT starts at 5
    assert inf.bl("PINTERACT")
    inf.ntruth["PHELP"] = 2
    assert not inf.bl("PHELP")


def test_pexit_does_not_win_on_a_single_insult(bb):
    inf, _ = _infer(bb, "H3110")
    # IF219/IF220 add to PEXIT but it stays below the 5 threshold after one turn
    assert inf.score("PEXIT") < 5


def test_forward_chaining_hostile_to_unsociable(bb):
    inf, _ = _infer(bb, "H3110")   # asserts DHOSTILE
    # IF940: *DSOCIABLE follows from DHOSTILE (doctor is not friendly)
    assert "DHOSTILE" in inf.truth
    assert "*DSOCIABLE" in inf.truth


# --- integration ------------------------------------------------------------

@pytest.fixture
def parry():
    return Parry(version="STRONG", seed=1)


def test_insult_raises_hurt(parry):
    before = parry.model.affect.hurt
    parry.respond("you are crazy")
    assert parry.model.affect.hurt > before   # HURT now rises (was flat before)


def test_insult_triggers_paranoia(parry):
    parry.respond("you are crazy")
    assert parry.turns[-1].intent == "PPARANOIA"
    # PARANOIA projects distrust onto the doctor
    assert "*DTRUSTWORTHY" in parry.inference.truth


def test_neutral_question_stays_calm(parry):
    parry.respond("how old are you?")
    a = parry.model.affect
    assert a.hurt == 5.0 and a.fear == 5.0    # no emotional spike
    assert parry.turns[-1].intent not in ("PPARANOIA", "PEXIT2")


def test_mild_less_sensitive_than_strong():
    strong = Parry(version="STRONG", seed=1)
    mild = Parry(version="MILD", seed=1)
    strong.respond("you are crazy")
    mild.respond("you are crazy")
    assert mild.model.affect.hurt < strong.model.affect.hurt


def test_sustained_hostility_ends_interview(parry):
    for _ in range(6):
        parry.respond("you are a stupid crazy liar")
        if parry.ended:
            break
    assert parry.ended is True
