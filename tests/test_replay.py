"""The port against recorded interviews (pyranoid/data/transcripts)."""

from __future__ import annotations

from pyranoid.replay import load, replay, summarise


def test_transcripts_parse():
    version, pairs = load("waits74-love")
    assert version == "STRONG" and len(pairs) == 20 and pairs[1][0] == "COULD YOU TELL ME YOUR NAME."
    assert pairs[0][2] == {"fear": 5.0, "anger": 5.0, "mistrust": 5.0, "shame": 5.0}


def test_against_the_1974_program_in_the_emulator():
    # PARRY.DMP (Nov 1974) run on the WAITS disk image, on the same PDATZ, with
    # its emotion trace on: the whole sample script of Colby's ALL.DOC.
    _, rows = replay("waits74-love")
    verdicts = [r["verdict"] for r in rows]
    # the front-end match and the memory lookup agree wherever no intention fires
    assert [i for i, v in enumerate(verdicts) if v == "exact"] == [0, 1, 2, 3, 5, 9, 11, 12, 14, 17, 18]
    assert [i for i, v in enumerate(verdicts) if v == "same set"] == [4, 8, 10]     # RANDOM's pick
    assert "absent" not in verdicts                          # every 1974 sentence is in the memory
    # the six differences are the CMU PPARANOIA (its reply groups have no units
    # in the 1974 PDAT, so REACT3 recovers) and the flare lead one turn earlier
    assert all(rows[i]["trace"] == "INTENT" for i in (6, 7, 13, 15, 19))
    # the affect levels agree with the program's own trace after every turn
    assert all(r["affect_same"] for r in rows)
    assert rows[-1]["affect"] == {"fear": 14.88, "anger": 12.85, "mistrust": 14.25, "hurt": 9.0}


def test_a_second_1974_run_varies_only_within_response_sets():
    _, rows = replay("waits74-love-2")
    counts = summarise(rows)
    assert len(rows) == 20 and counts["absent"] == 0
    assert counts["exact"] + counts["same set"] >= 13


def test_the_1972_rfc_439_sentences_are_mostly_in_the_1974_memory():
    _, rows = replay("rfc439")
    counts = summarise(rows)
    assert counts["exact"] + counts["same set"] + counts["in memory"] >= 46
    assert len(rows) == 63


def test_the_1971_paper_excerpts_replay_without_error():
    for name in ["colby71-1", "colby71-2", "colby71-3", "colby71-4", "colby71-5", "colby71-6"]:
        _, rows = replay(name)
        assert rows and all(r["reply"].strip() for r in rows if r["recorded"])
