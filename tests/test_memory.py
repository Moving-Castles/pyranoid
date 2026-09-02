"""The memory layer: PDAT linking, expression, anaphora, stories, beliefs."""

from __future__ import annotations

import pytest

from pyranoid.lisp import NIL, Pair, T, read_file
from pyranoid.parry import DATA_DIR, Parry


@pytest.fixture
def p():
    return Parry(seed=1, strict=True)


# --- BEL / ENG ----------------------------------------------------------------

def test_load_counts_and_quirks(p):
    units = p.plist.atoms_with("BONDVALUE")
    sets = p.plist.atoms_with("NORMAL")
    assert len(units) == 659 and len(sets) == 521
    # the one duplicate #E record is logged, not hidden
    assert [e[:2] for e in p.ERROR_LIST] == [["BAD INPUT-DOUBLE ENTRY", "B5420"]]
    # the one dangling RESP reference
    assert p.getprop("H4897", "RESP") == "B0284" and not p.getprop("B0284", "INCORE")


def test_unit_properties(p):
    assert p.getprop("H0050", "BONDVALUE") == ["LOCATION", "I", "HOSPITAL"]
    assert p.getprop("H0050", "TOPIC") == ["HOSPITAL"]
    assert p.getprop("H0050", "RESP") == "B0080"
    assert p.getprop("H0050", "ANAPH") == [Pair("WHY", "H0300")]
    assert p.getprop("B0920", "EXH") is T
    assert p.getprop("H0045", "SF") == ["ENDROUTINE"]
    assert p.getprop("H0042", "FX")[0] == "COND"
    assert p.getprop("H3000", "NN")[0] == "PROG2"            # loaded, never run
    assert p.getprop("H3000", "CLASS") == "INSULT"


def test_pdatb_change_rdata_bel_inf(p):
    assert p.getprop("HELLO", "IND") == "H0042"
    assert p.getprop("H0010", "UNIT") == "GO_ON" and p.getprop("REASON", "UNIT") == "H0030"
    assert p.getprop("H5218", "MEQV") == "H5210"
    assert p.getprop("BOOKIESET", "WT") == 9 and p.getprop("BOOKIESET", "NEXT") == "RACKETSET"
    assert p.getprop("CROOK", "SET") == "BOOKIESET" and p.getprop("GUN", "STRONG") is T
    assert p.getprop("DELNSET", "STORY")[:3] == ["H1010", "H1020", "H1050"]
    assert p.getprop("H1020", "STORYNAME") == "DELNSET"
    assert p.INTLIST[0] == "PINTERACT" and p.INTLIST[-1] == "PEXIT2"
    assert p.getprop("PEXIT2", "CLASS") == "INN" and p.getprop("DCHELP", "OPPOS") == "*DCHELP"
    assert p.getprop("DBABNORMAL", "EMOTE") == [["AJUMP", 0.4], ["FJUMP", 0.4], ["HJUMP", 0.3]]
    assert p.getprop("IF940", "THEOREM") == ["*DSOCIABLE", "DHOSTILE"]
    assert "IF940" in p.getprop("DHOSTILE", "TH")


# --- EXPRESS / SELSENTENCE / SAY --------------------------------------------

def test_selsentence_is_destructive_and_ordered_when_exh(p):
    sents = list(p.getprop("B0920", "NORMAL"))              # H1010's response set, EXH T
    assert p.express("H1010", "RESP") == sents[0]           # in order
    assert p.express("H1010", "RESP") == sents[1]
    assert len(p.getprop("B0920", "NORMAL") or []) == len(sents) - 2


def test_exhausted_set_sets_the_flag(p):
    p.putprop("B0080", NIL, "NORMAL")
    assert p.express("H0050", "RESP") is NIL
    assert p.EXHAUST is T


def test_embedded_reference_expresses_the_slot_unit(p):
    # H0080 = (REASON H0070 H0100) has no RESP: it goes through REASON's unit,
    # whose sentences are ((2 RESP NORMAL)) -> express slot 2 = H0100
    words = p.express("H0080", "RESP")
    assert words in p.getprop("B0130", "NORMAL") + [words]      # one of H0100's sentences
    assert words != [[2, "RESP", "NORMAL"]]


def test_express_adds_anaphora_for_the_next_input(p):
    p.express("H0050", "RESP")
    assert p.get_anaph("WHY") is NIL                            # not yet current
    p.ANAPHLIST = p.ANAPHLISTNEW
    assert p.get_anaph("WHY") == "H0300"
    assert p.get_anaph("THERE") == "HOSPITAL"
    assert p.get_anaph("WHERE") == "H0062"                      # via !ALLANAPHS (THERE WHERE)


# --- SPECFN / GET_STORY -----------------------------------------------------

def test_specfn_resolves_or_quits(p):
    assert p.specfn("H0440") is NIL                             # not an anaphor
    assert p.specfn("H0030") == "QUIT"                          # WHY with nothing to refer to
    p.ANAPHLIST = [Pair("WHY", "H0300")]
    assert p.specfn("H0030") == "H0300"


def test_get_story_advances_the_topic_story(p):
    p.REACTTO = "H0460"                                         # topic JOB -> set WORK
    assert p.getprop("WORK", "STORY") == ["H0460", "H0462", "H0490"]
    assert p.get_story() == "H0460"
    assert p.getprop("WORK", "STORY") == ["H0462", "H0490"]
    assert p.get_story() == "H0462"


def test_flare_story_leads_on_to_the_next_flare(p):
    p.REACTTO = "H1000"                                         # HORSESET
    p.putprop("HORSESET", NIL, "STORY")
    p.FLARE = "HORSE"
    unit = p.get_story()                                        # FLSTMT -> LEADON -> FLARELEAD
    assert unit == "H2617"                                      # NEXTFL lead-in
    assert p.FLARE == "HORSERACING" and p.WDFLAG == ["HORSERACING"]
    assert "HORSESET" in p.DEADFLARES


# --- the belief machinery ---------------------------------------------------------

def test_assert_addto_bl_and_emote(p):
    assert p.bl("PINTERACT") is T and p.bl("PHELP") is NIL
    p.addto("PHELP", 5)
    assert p.get0("PHELP", "NTRUTH") == 7 and p.bl("PHELP") is T
    p.addto("PHELP", 20)
    assert p.get0("PHELP", "NTRUTH") == 9                       # intentions clamp at 9
    p.assert2("DBABNORMAL")
    assert p.bl("DBABNORMAL") is T
    assert p.HJUMP == 0.3 and p.FJUMP == 0.4 and p.AJUMP == 0.4  # its EMOTE rules
    assert "DBABNORMAL" in p.PARBEL


def test_addto_propagates_half_to_th2_parents_with_fixnum_division(p):
    p.addto("BADJOB", 2)                                        # TH2 LOSER
    assert p.get0("LOSER", "NTRUTH") == 1
    assert p.HJUMP == 0.1                                       # EMOTE (HJUMP 0.2) halved


def test_inference_forward_chains(p):
    p.REACTTO = "H3110"
    p.STOPIC = "STRONGFEELINGS"
    p.INPUTNO = 1
    p.inference()
    assert p.bl("DHOSTILE") is T and p.bl("*DSOCIABLE") is T    # IF940
    assert p.get0("PEXIT", "NTRUTH") < 5


# --- authentic quirks ----------------------------------------------------------------

def test_andthen_never_sets_lastin_and_repetition_never_fires(p):
    p.andthen(["IN", "H0440"])
    p.andthen(["OUT", "H0440"])
    assert p.CLIST == [["OUT", "H0440"], ["IN", "H0440"]]
    assert p.LASTIN is NIL and p.LASTOUT is NIL
    assert p.repetition("H0440", "IN") is NIL


def test_paranoid_reply_groups_are_absent_from_the_1974_data(p):
    absent = [f[1] for f in read_file(DATA_DIR / "pdatb") if f[3] == "IND" and not p.getprop(f[2], "INCORE")]
    assert absent == ["PACCUSE", "PDISTANCE", "PHOSTILEREPLIES", "PANGER", "PPERS", "PCAUTION",
                      "PAFRAID", "PTHREATQ", "PBELIEVEREPLIES", "PALOOF"]
