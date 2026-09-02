"""Tests for the PDAT loader, run against the recovered PDATZ text file."""

from __future__ import annotations

import pytest

from pyranoid.data import DATA_DIR
from pyranoid.pdat import (  # type: ignore
    DottedPair,
    _normalise,
    _read_forms,
    _Reader,
    load_pdat,
)

PDATZ = DATA_DIR / "pdatz.txt"


# --- reader unit tests ------------------------------------------------------

def read_one(text):
    return _Reader(text).read()


def test_atom_and_list():
    assert read_one("HELLO") == "HELLO"
    assert read_one("(A B C)") == ["A", "B", "C"]
    assert read_one("(A (B C) D)") == ["A", ["B", "C"], "D"]


def test_bracket_list_like_paren():
    assert read_one("[PROG2 (SETQ X 1) NIL]") == ["PROG2", ["SETQ", "X", "1"], "NIL"]


def test_dotted_pair():
    r = read_one("(WHY . H0300)")
    assert isinstance(r, DottedPair)
    assert r.car == "WHY" and r.cdr == "H0300"


def test_dotted_pair_no_spaces():
    r = read_one("(THEY.MAFIA)")
    assert isinstance(r, DottedPair)
    assert r.car == "THEY" and r.cdr == "MAFIA"


def test_decimal_not_dotted():
    # 0.2 is a number, not a dotted pair
    assert read_one("(SETQ AJUMP 0.2)") == ["SETQ", "AJUMP", "0.2"]


def test_slash_escape_literal_punct():
    # "GANGSTERS/." is the single word "GANGSTERS."
    assert read_one("(GANGSTERS/. THEY)") == ["GANGSTERS.", "THEY"]
    assert read_one("(OK/,)") == ["OK,"]


def test_glyph_normalisation():
    assert _normalise("λ0050") == "H0050"
    assert _normalise("α0080") == "B0080"
    assert _normalise("@λ0010") == "@H0010"
    assert read_one("(#B λ0050 100 (LOCATION I HOSPITAL))")[1] == "H0050"


def test_multiple_top_level_forms():
    forms = list(_read_forms("(#B λ1 0 (A)) (#E α1 NORMAL ((HI)))"))
    assert forms[0][0] == "#B" and forms[1][0] == "#E"


# --- integration against recovered PDATZ ------------------------------------

@pytest.fixture(scope="module")
def mem():
    if not PDATZ.exists():
        pytest.skip(f"recovered file missing: {PDATZ}")
    return load_pdat(PDATZ)


def test_counts_match_recovery(mem):
    # Recovery verified 659 belief units and 522 #E records. One #E id (B5420)
    # is defined twice in Colby's source, so there are 521 unique response units.
    assert len(mem.beliefs) == 659
    assert len(mem.responses) == 521
    assert mem.duplicate_names == ["B5420"]


def test_hospital_unit(mem):
    b = mem.beliefs["H0050"]
    assert b.concept == ["LOCATION", "I", "HOSPITAL"]
    assert b.weight == 100
    assert b.topic == ["HOSPITAL"]
    assert b.resp == "B0080"
    assert b.anaph == {"WHY": "H0300"}


def test_hospital_response_sentences(mem):
    e = mem.responses["B0080"]
    texts = [r.words for r in e.normal]
    assert "I AM IN THE HOSPITAL" in texts
    assert "I AM IN THE PALO ALTO VA HOSPITAL" in texts
    # anaphora targets recovered as an assoc map
    assert e.anaph["HOW_LONG"] == "H0130"
    assert e.anaph["THERE"] == "HOSPITAL"


def test_mafia_delusion(mem):
    e = mem.responses["B0940"]  # (IS_AFTER MAFIA I)
    texts = [r.words for r in e.normal]
    assert "THEY ARE OUT TO GET ME" in texts
    assert "THEY ARE AFTER ME" in texts


def test_exhaust_flag(mem):
    # α0920 has EXH T in the recovered text
    assert mem.responses["B0920"].exhaust is True


def test_response_for_helper(mem):
    e = mem.response_for("H0050")
    assert e is not None and e.name == "B0080"


def test_escaped_punctuation_in_response(mem):
    # α0932: "...GANGSTERS/. THEY CONTROL..." -> literal period kept, joined text
    e = mem.responses["B0932"]
    joined = " ".join(r.words for r in e.normal)
    assert "GANGSTERS. THEY CONTROL" in joined


def test_dangling_resps_are_the_known_authentic_ones(mem):
    # The source has exactly one dangling RESP: H4897 -> B0284 (never defined).
    # all.doc documents this class of original-data bug. The loader must expose
    # it rather than silently repair or drop it.
    assert mem.dangling_responses() == {"H4897": "B0284"}
