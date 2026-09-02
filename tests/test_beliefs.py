"""Tests for the belief/inference data loader (bel, inf)."""

from __future__ import annotations

import pytest

from pyranoid.beliefs import BeliefBase


@pytest.fixture(scope="module")
def bb():
    return BeliefBase.load()


def test_belief_counts_and_classes(bb):
    from collections import Counter
    by = Counter(b.cls for b in bb.beliefs.values())
    assert by["HUM"] == 5 and by["HUM2"] == 15   # 20 self-beliefs
    assert by["DOC"] == 28                        # doctor beliefs
    assert by["INN"] == 16                        # intentions


def test_complement_parsing(bb):
    d = bb.beliefs["DCHELP"]
    assert d.value == 4.0 and d.complement == "*DCHELP" and d.complement_value == 2.0


def test_intentions_in_priority_order(bb):
    ints = bb.intentions()
    # bel lists intentions low -> high priority; PEXIT2 is last (highest)
    assert ints[0] == "PINTERACT"
    assert ints[-1] == "PEXIT2"
    assert "PPARANOIA" in ints and "PSTRONGFEEL" in ints


def test_emote_rules(bb):
    assert len(bb.emotes) == 9
    hjump = [e for e in bb.emotes if e.jump == "HJUMP"]
    # being called crazy/dumb/loser/lying drives HURT
    assert any({"CRAZY", "DUMB", "LOSER", "LYING"} <= set(e.beliefs) for e in hjump)


def test_th2_rules(bb):
    assert len(bb.th2_responses) == 32
    # CRAZY is grouped from PARANOID/NEEDHOSP/NEEDTREATMENT
    crazy = [g for g in bb.th2_groups if g.name == "CRAZY"]
    assert crazy and "PARANOID" in crazy[0].members


def test_if_rules_parsed(bb):
    assert len(bb.rules) == 75
    pexit = [r for r in bb.rules if r.tag == "IF215"]
    assert pexit and pexit[0].consequent == ["PEXIT", "2"]
    assert "DDHARM" in pexit[0].antecedents
