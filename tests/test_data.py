"""Tests for the lexical/pattern data loaders."""

from __future__ import annotations

import pytest

from pyranoid.data import DATA_DIR, Lexicon

SRC = DATA_DIR


@pytest.fixture(scope="module")
def lex():
    if not (SRC / "dictio").exists():
        pytest.skip("original source missing")
    return Lexicon.load(SRC)


def test_entry_counts(lex):
    assert len(lex.synonyms) == 1857
    assert len(lex.spats) == 3549
    assert len(lex.cpats) == 1196
    assert len(lex.idioms) == 182
    assert len(lex.nearby) == 8
    assert len(lex.flags) == 9


def test_dictio_pos_vs_canon(lex):
    assert lex.dictio["ABNORMAL"].kind == "canon"
    assert lex.dictio["ABNORMAL"].value == "ODD"
    assert lex.dictio["ATTEND"].tokens == ["GO", "TO"]
    # a part-of-speech entry
    assert lex.dictio[","].kind == "pos"


def test_unit_targets_normalised(lex):
    # ^H (0x08) prefix became 'H'
    assert lex.spats[1].target == "H1410"
    assert all(t.target[0] in "HP" for t in lex.spats)
    assert all(t.target[0] == "H" for t in lex.cpats)  # cpat targets are all H


def test_idiom_empty_replacement(lex):
    empties = [ph for ph, rep in lex.idioms if not rep]
    assert ("APPEAR", "TO") in empties


def test_affix_table(lex):
    ed = [a for a in lex.suffix if a.affix == "ED"]
    assert ed and ed[0].base_pos == "verb" and ed[0].action == ["past"]


def test_unit_pairs_handle_nil(lex):
    # famly.pat contains a (NIL UNIT) pair -> (None, "...")
    assert any(a is None for a, b in lex.famly)
