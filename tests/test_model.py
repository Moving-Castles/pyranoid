"""Tests for the paranoid affect model, checking the ported dynamics."""

from __future__ import annotations

from pyranoid.model import CEIL, Model


def test_version_baselines():
    assert Model("MILD").affect.fear == 0.0
    strong = Model("STRONG").affect
    assert strong.fear == strong.anger == strong.mistrust == strong.hurt == 5.0
    assert Model("WEAK").weak is True


def test_fear_jump_saturates_toward_ceiling():
    m = Model("MILD")
    m.fjump = 0.5
    m.raise_affect()
    # fear = 0 + 0.5*(20-0) = 10 ; mistrust = 0 + 0.25*20 = 5
    assert abs(m.affect.fear - 10.0) < 1e-9
    assert abs(m.affect.mistrust - 5.0) < 1e-9
    # in-spec jumps approach the ceiling from below but never cross it
    for _ in range(50):
        m.fjump = 0.6
        m.raise_affect()
    assert m.affect.fear <= CEIL + 1e-9
    assert m.affect.fear > 19.0  # but does get very close


def test_mistrust_base_drifts_up_permanently():
    m = Model("MILD")
    before = m.affect.mistrust0
    m.fjump = 0.5
    m.raise_affect()
    assert m.affect.mistrust0 > before  # sensitisation is permanent


def test_hurt_raises_floor_on_fear_and_anger():
    m = Model("MILD")
    m.hjump = 1.0
    m.raise_affect()
    # hurt jumps to 20; hurt0 -> 10; fear0/anger0 -> >=5
    assert m.affect.hurt0 >= 10.0
    assert m.affect.fear0 >= 5.0 and m.affect.anger0 >= 5.0


def test_weak_version_scales_jumps_down():
    strong, weak = Model("MILD"), Model("WEAK")
    strong.fjump = weak.fjump = 0.5
    strong.raise_affect()
    weak.raise_affect()
    assert weak.affect.fear < strong.affect.fear


def test_decay_returns_toward_base():
    m = Model("MILD")
    m.fjump = 0.5
    m.raise_affect()
    high = m.affect.fear
    m.modify_vars()
    assert m.affect.fear < high  # decays
    assert m.fjump is None       # jumps cleared


def test_check_flare_picks_highest_weight():
    m = Model("STRONG")
    # RACKETEERS (RACKETSET, wt 17) beats HORSES (HORSESET, wt 1)
    assert m.check_flare(["HORSES", "RACKETEERS"], m.live_flares, mark=False)
    assert m.flare == "RACKETSET"


def test_flare_reference_raises_fear_and_marks_dead():
    m = Model("STRONG")
    m.flare_reference(["BOOKIES"])
    assert "BOOKIESET" in m.dead_flares
    assert m.fjump is not None and m.fjump > 0


def test_delusion_reference_sets_delflag_and_fear():
    m = Model("STRONG")
    m.delusion_reference(found_strong=True)
    assert m.delflag is True
    assert m.topic == "DELUSIONS"
    assert m.fjump == 0.5  # first delusion reference


def test_modifvar_keeps_fear_floor_when_delusional():
    m = Model("MILD")
    m.delflag = True
    m.affect.fear = 10
    m.modify_vars()
    assert m.affect.fear >= m.affect.fear0 + 5  # delusion floor


def test_angermode_and_fearmode_thresholds():
    m = Model("STRONG")
    m.affect.anger = 18
    assert m.angermode() == "ANGER"
    m.affect.anger = 10
    assert m.angermode() == "HOSTILEREPLIES"
    m.affect.fear = 19
    assert m.fearmode() == "EXIT"
    m.affect.fear = 15
    assert m.fearmode(is_question=True) == "THREATQ"
    assert m.fearmode(is_question=False) == "AFRAID"


def test_anger_fear_mode_defers_on_flare_topic():
    m = Model("STRONG")
    assert m.anger_fear_mode("MAFIASET") is None
    assert m.anger_fear_mode("STRONGFEELINGS") is None


def test_paranoid_intent_activation():
    m = Model("STRONG")
    m.affect.hurt = 8
    assert m.paranoid_intent() == "PPARANOIA"
    m2 = Model("MILD")
    m2.affect.fear = 15
    assert m2.paranoid_intent() == "PSTRONGFEEL"
