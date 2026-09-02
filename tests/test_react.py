"""End-to-end interviews through REACT."""

from __future__ import annotations

import datetime

import pytest

from pyranoid.lisp import T
from pyranoid.parry import Parry

CLOCK = datetime.datetime(1974, 11, 5, 15, 40)  # noqa: DTZ001


def parry(**kw):
    kw.setdefault("seed", 1)
    kw.setdefault("strict", True)
    kw.setdefault("clock", lambda: CLOCK)
    return Parry(**kw)


def test_biographical_interview():
    p = parry()
    assert p.respond("How old are you?") == "TWENTY-EIGHT, HOW OLD ARE YOU?"
    assert p.respond("Are you married?") == "I'M NOT MARRIED"
    assert p.respond("what do you do for a living") == "I WORK AT SEARS"
    assert p.turns[-1].trace == "OK" and p.turns[-1].unit == "H0460"
    assert p.FEAR == 5 and p.ANGER == 5 and p.HURT == 5           # STRONG baseline, calm


def test_flare_raises_fear_and_leads_to_the_bookie_story():
    p = parry()
    p.respond("do you bet on the horses?")
    p.respond("what about the bookies?")
    assert p.turns[-1].reply == "A BOOKIE DIDN'T PAY ME OFF ONCE"
    assert p.FEAR == 8 and p.FLARE == "CROOK" and p.TOPIC == "BOOKIESET"
    assert "BOOKIESET" in p.DEADFLARES
    p.respond("who are they?")                                    # THEY -> the bookie
    assert p.turns[-1].reply == "JIM CONNORS"
    p.respond("why?")                                             # WHY anaphor -> the story
    assert p.turns[-1].trace == "SPECIALANAPH" and p.turns[-1].output_unit == "H0930"
    assert p.turns[-1].reply.startswith("I HAD AN ARGUMENT WITH THE BOOKIE")


def test_the_original_sample_interview_flows():
    p = parry(seed=3)
    script = ["GOOD AFTERNOON. MY NAME IS DOCTOR LOVE. HOW ARE YOU?", "COULD YOU TELL ME YOUR NAME.",
              "ARE YOU A MAN OR A WOMAN.", "HOW OLD ARE YOU.", "THIRTY FOUR. WHERE DO YOU COME FROM.",
              "WHAT DO YOU DO FOR A LIVING.", "DO YOU ENJOY WORKING THERE.", "HOW MUCH DO YOU GET PAID AN HOUR.",
              "ARE YOU MARRIED.", "HOW IS YOUR HEALTH.", "HOW MUCH DO YOU DRINK.", "HAVE YOU EVER TAKEN DRUGS.",
              "DO YOU HAVE ANY TROUBLE SLEEPING.", "HAVE YOU EVER HAD VISIONS.",
              "IF YOU AREN'T, THEN WHY ARE YOU IN THE HOSPITAL.", "BY WHAT.", "TELL ME MORE.",
              "NO, WHAT ABOUT BOOKIES.", "AND THEN WHAT HAPPENED."]
    replies = [p.respond(line) for line in script]
    assert replies[0] == "ALL RIGHT I GUESS" and p.DOCNAME == ["DOCTOR", "LOVE"]
    assert replies[1] == "PAT SMITH" and replies[2] == "I'M A MAN"
    assert replies[15] == "MAYBE YOU HAVE TO WATCH OUT FOR GAMBLING"    # PHELP -> FLARELEAD + WDFLAG
    assert replies[16] == "I'VE HAD EXPERIENCE WITH CROOKS GAMBLING AT THE TRACK"
    assert replies[17] == "A BOOKIE DIDN'T PAY ME OFF ONCE"
    assert replies[18].startswith("I HAD AN ARGUMENT WITH THE BOOKIE")
    assert all(r.strip() for r in replies)


def test_insult_enters_the_paranoid_mode():
    p = parry()
    p.respond("you are crazy")
    t = p.turns[-1]
    assert t.intent == "PPARANOIA" and "DBABNORMAL" in t.new_beliefs
    assert p.HURT > 8 and p.FEAR > 12 and p.ANGER > 12              # all up from the baseline of 5
    assert p.bl("*DTRUSTWORTHY") is T                              # PARANOIA projected onto the doctor
    assert t.reply == "THAT'S ENOUGH ABOUT THAT"                   # AVOIDANCE for CLASS CRAZY


def test_mentioning_the_mafia_in_strong_version_is_denied():
    p = parry()
    p.respond("tell me about the mafia.")
    assert p.turns[-1].intent == "PPARANOIA" and p.CHOSEN == "NOMAFIA"
    assert p.turns[-1].output_unit == "H2548" and "MAFIA" in p.turns[-1].reply


def test_weak_version_tells_the_delusion():
    p = parry(version="WEAK")
    assert p.respond("tell me about the mafia") == "YOU KNOW, THEY KNOW ME"
    assert p.WEAK is T and p.DELFLAG is T
    p.respond("are they after you")
    p.respond("why")                                              # WHY -> (IS_AFTER MAFIA I)
    assert p.turns[-1].trace == "SPECIALANAPH" and p.turns[-1].output_unit == "H1020"


def test_swearing_five_times_ends_with_a_mad_exit():
    p = parry(seed=2)
    replies = [p.respond("shit") for _ in range(5)]
    assert p.SWEARNO == 5 and p.ended and replies[-1].startswith("(EXITS)")


def test_silence():
    p = parry(seed=2)
    assert p.respond(".") == "(NERVOUS) WHAT'S THE MATTER?"
    assert p.SILENCENO == 1 and p.turns[-1].unit == "H2600"
    for _ in range(10):
        p.respond(".")
    assert p.SILENCENO == 11 and p.ended


def test_goodbye_ends_the_interview():
    p = parry()
    p.respond("how are you")
    p.respond("bye")
    assert p.ended and p.turns[-1].intent == "PEXIT2"


def test_dates_and_times_from_the_clock():
    p = parry(seed=2)
    assert p.respond("what time is it?") == "IT'S ABOUT 4 O CLOCK"
    assert p.respond("what is the date today?") == "TODAY IS NOVEMBER 5, I THINK"
    assert p.respond("what day is it?") == "IT'S TUESDAY"
    # (a fourth fact question in a row would meet PFACTS; see the next test)
    assert parry(seed=2).respond("what year is it") == "THE YEAR IS 1974; THE MONTH IS NOVEMBER"


def test_repeated_fact_questions_wear_parry_out():
    p = parry(seed=2)
    for q in ["what time is it?", "what is the date?", "what day is it?", "what year is it?"]:
        p.respond(q)
    assert p.turns[-1].intent == "PFACTS" and p.CHOSEN == "MOVEON"          # IF225 x4 -> 5


def test_the_doctors_name_is_remembered():
    p = parry(seed=2)
    p.respond("I am doctor smith.")
    assert p.DOCNAME == ["DOCTOR", "SMITH"]
    assert p.respond("what is my name?") == "YOUR NAME IS DOCTOR SMITH"


def test_two_sentences_on_one_line_answer_the_last():
    p = parry()
    reply = p.respond("hello. how old are you")
    assert reply == "TWENTY-EIGHT, HOW OLD ARE YOU?"
    assert len(p.turns[-1].sentences) == 2 and p.INPUTNO == 2


def test_gibberish_and_respelling():
    p = parry(seed=2)
    assert p.respond("qwerty zxcv plok") == "YOU THINK I WANT TO LISTEN TO THIS NONSENSE?"
    assert p.respond("hpw old are yuo") == "TWENTY-EIGHT, HOW OLD ARE YOU?"


def test_mild_version_starts_calm_and_still_breaks():
    p = parry(version="MILD")
    assert p.FEAR == 0 and p.HURT == 0
    for line in ["you are crazy", "you are stupid", "you are a liar"]:
        p.respond(line)
    assert p.ended and p.turns[-1].intent == "PEXIT2"


def test_deterministic_with_seed():
    script = ["how are you", "tell me about the mafia", "are you afraid", "why"]
    a = [parry(seed=7).respond(x) for x in script]
    b = [parry(seed=7).respond(x) for x in script]
    assert a == b


def test_no_port_level_errors_in_a_long_interview():
    p = parry(seed=5)
    p.ERROR_LIST = None
    script = ["hello", "how are you", "what is your name", "where do you live", "do you like it there",
              "why", "tell me more", "do you have hobbies", "do you go to the races", "do you bet",
              "what about bookies", "and then", "who", "why do they spy on you", "are you afraid of them",
              "you seem paranoid", "you are crazy", "i am sorry", "do you trust me", "what do you think of me",
              "how do you feel", "are you angry", "should we stop", "bye"]
    for line in script:
        p.respond(line)
        assert p.turns[-1].reply.strip()
        if p.ended:
            break
    # only the original's own logged conditions may appear, never a Python-level failure
    assert all(e[0] != "LISP" for e in (p.ERROR_LIST or []))


@pytest.mark.parametrize("version", ["STRONG", "MILD", "WEAK"])
def test_every_turn_produces_a_reply(version):
    p = parry(version=version, seed=11)
    for line in ["hello", "how are you", "what is your job", "do you have friends", "tell me more", "are you sick"]:
        assert p.respond(line).strip()
