"""The port against recorded interviews (pyranoid/data/transcripts)."""

from __future__ import annotations

from pyranoid.replay import load, replay, summarise


def test_transcripts_parse():
    version, pairs = load("waits74-love")
    assert version == "STRONG" and len(pairs) == 10 and pairs[1][0] == "COULD YOU TELL ME YOUR NAME."


def test_against_the_1974_program_in_the_emulator():
    # PARRY.DMP (Nov 1974) run on the WAITS disk image, on the same PDATZ.
    # Turns answered from the front-end match and a plain memory lookup are
    # identical; the divergences are in routines the CMU source revised after
    # this image (CHECKINPUT/AFFECT/PPARANOIA) and in RANDOM's sentence choice.
    _, rows = replay("waits74-love")
    verdicts = [r["verdict"] for r in rows]
    assert verdicts[0] == "exact"            # ALL RIGHT I GUESS
    assert verdicts[2] == "exact"            # TWENTY-EIGHT, HOW OLD ARE YOU?
    assert verdicts[3] == "exact"            # I WORK AT SEARS
    assert verdicts[4] in ("exact", "same set")   # I'VE BEEN UPSET LATELY / I'M QUITE UPSET
    assert verdicts[6] == "exact"            # A BOOKIE DIDN'T PAY ME OFF ONCE
    assert verdicts[7] == "exact"            # the bookie story (SPECIALANAPH)
    assert all(v != "absent" for v in verdicts)   # every 1974 sentence is in the memory
    # the affect levels the 1974 program printed at the end
    assert rows[-1]["affect"]["fear"] == 14.48 and rows[-1]["affect"]["anger"] == 10.85


def test_against_the_full_1974_interview():
    # the whole ALL.DOC script put to PARRY.DMP (its greeting line was swallowed
    # by the start-up prompts, so the record starts at the second line)
    _, rows = replay("waits74-love-full")
    counts = summarise(rows)
    assert len(rows) == 40 and counts["absent"] == 0     # every 1974 sentence is in the memory
    assert counts["exact"] + counts["same set"] >= 12


def test_the_1972_rfc_439_sentences_are_mostly_in_the_1974_memory():
    _, rows = replay("rfc439")
    counts = summarise(rows)
    assert counts["exact"] + counts["same set"] + counts["in memory"] >= 46
    assert len(rows) == 63


def test_the_1971_paper_excerpts_replay_without_error():
    for name in ["colby71-1", "colby71-2", "colby71-3", "colby71-4", "colby71-5", "colby71-6"]:
        _, rows = replay(name)
        assert rows and all(r["reply"].strip() for r in rows if r["recorded"])
