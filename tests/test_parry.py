"""End-to-end tests for the PARRY agent."""

from __future__ import annotations

import pytest

from pyranoid.data import DATA_DIR
from pyranoid.parry import Parry


@pytest.fixture
def parry():
    if not (DATA_DIR / "dictio").exists():
        pytest.skip("data missing")
    return Parry(version="STRONG", seed=1)


def test_biographical_facts(parry):
    # PARRY answers the standard interview with Pat Smith's facts
    assert "PAT SMITH" in parry.respond("What is your name?")
    assert "TWENTY-EIGHT" in parry.respond("How old are you?").upper()
    assert "MARRIED" in parry.respond("Are you married?").upper()


def test_mafia_raises_fear_and_mistrust(parry):
    before = parry.model.affect.fear
    parry.respond("Tell me about the mafia.")
    assert parry.model.affect.fear > before
    assert parry.model.delflag is True  # delusion engaged


def test_emotions_escalate_over_paranoid_topics(parry):
    for line in ["Do you know the mafia?", "Are they after you?",
                 "Why would the mafia care about you?"]:
        parry.respond(line)
    # fear ends well above the strong-version baseline of 5
    assert parry.model.affect.fear > 10


def test_swearing_provokes_anger(parry):
    parry.respond("you are a bastard")
    assert parry.model.affect.anger > 5.0


def test_goodbye_ends_interview(parry):
    parry.respond("goodbye")
    assert parry.ended is True


def test_every_turn_produces_nonempty_reply(parry):
    for line in ["hello", "how are you", "what is your job",
                 "do you have friends", "tell me more", "are you sick"]:
        r = parry.respond(line)
        assert isinstance(r, str) and r.strip()


def test_trace_diagnostics_populated(parry):
    parry.respond("How old are you?")
    assert parry.turns[-1].trace in {
        "OK", "SPECIALANAPH", "KEYWORD", "NO_PATTERN", "INTENT",
    }


def test_deterministic_with_seed():
    a = Parry(version="STRONG", seed=7)
    b = Parry(version="STRONG", seed=7)
    script = ["how are you", "tell me about the mafia", "are you afraid"]
    assert [a.respond(x) for x in script] == [b.respond(x) for x in script]
