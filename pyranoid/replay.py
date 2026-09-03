"""Replay a recorded interview and compare the port's replies with the record.

    python -m pyranoid.replay                 # every transcript in data/transcripts
    python -m pyranoid.replay rfc439 waits74-love

A transcript is a text file of ``I:`` (interviewer) and ``O:`` (PARRY) lines
with ``#`` comments; a ``# version:`` comment selects WEAK/MILD/STRONG, and
``#  FEAR = 5.00`` style comments after a reply are the program's own emotion
trace, compared with the port's levels after the same turn.  For each pair
the port is fed the interviewer's line and its reply is classed:

    exact     the same sentence
    same set  a sentence from the same response set (RANDOM picked another)
    in memory the recorded sentence exists in PDAT, the port chose a different set
    absent    the recorded sentence is not in the 1974 memory at all

The 1971 excerpts and the 1972 RFC session were produced by earlier versions
of the program and its data; only ``waits74-*`` (the November 1974 program
run in the emulator, on the same PDATZ) is a like-for-like reference.
"""

from __future__ import annotations

import re
import sys

from pyranoid.parry import DATA_DIR, Parry

TRANSCRIPTS = DATA_DIR / "transcripts"
_AFFECT = re.compile(r"#\s*(FEAR|ANGER|MISTRUST|SHAME)\s*=\s*([\d.]+)")
_AFFECT_KEYS = {"fear": "fear", "anger": "anger", "mistrust": "mistrust", "shame": "hurt"}


def normalise(text: str) -> str:
    """Comparable form of a sentence: upper case, punctuation dropped, and a
    leading non-verbal feature such as "(STARES AT YOU)" removed."""
    text = re.sub(r"^\s*\([^()]*\)\s*", "", text.strip())
    text = text.upper().replace("/,", ",")
    text = re.sub(r"[^A-Z0-9' ]+", " ", text)
    return " ".join(text.split())


def load(name: str):
    path = TRANSCRIPTS / f"{name}.txt"
    version, pairs, current = "STRONG", [], None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith("# version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("#"):
            m = _AFFECT.match(line)
            if m and current is not None:      # the program's own emotion trace
                current[2][m.group(1).lower()] = float(m.group(2))
        elif not line:
            continue
        elif line.startswith("I:"):
            current = [line[2:].strip(), "", {}]
            pairs.append(current)
        elif line.startswith("O:") and current is not None:
            current[1] = line[2:].strip()
    return version, pairs


def sentence_index(p: Parry) -> dict:
    """normalised sentence -> the response sets (#E units) that contain it."""
    index: dict = {}
    for unit in p.plist.atoms_with("NORMAL"):
        for words in p.getprop(unit, "NORMAL") or []:
            words = [w for w in words if isinstance(w, str)]   # drop a (NON VERBAL) lead
            index.setdefault(normalise(" ".join(words)), []).append(unit)
    return index


def lookup(index: dict, sentence: str) -> list:
    """The response sets a sentence comes from.  LASTWORD appends a word or
    two to a set's sentence (a flare lead is "WHAT DO YOU KNOW ABOUT" plus the
    flare word), so a sentence is also tried without its last one to three words."""
    words = sentence.split()
    for n in range(4):
        if n and n >= len(words):
            break
        sets = index.get(" ".join(words[:len(words) - n]) if n else sentence, [])
        if sets:
            return sets
    return []


def response_set(p: Parry, turn):
    out = turn.output_unit
    if isinstance(out, str) and out.startswith("B"):
        return out
    if isinstance(out, str):
        return p.getprop(out, "RESP")
    return None


def replay(name: str, seed: int = 0):
    version, pairs = load(name)
    p = Parry(seed=seed, version=version, strict=True)
    index = sentence_index(p)
    rows = []
    for asked, recorded, recorded_affect in pairs:
        reply = p.respond(asked)
        turn = p.turns[-1]
        affect_same = None
        if recorded_affect:
            # the 1974 NUMED truncated to two decimals where the CMU one rounds
            affect_same = all(abs(float(turn.affect.get(_AFFECT_KEYS[k], -1)) - v) < 0.011
                              for k, v in recorded_affect.items())
        want, got = normalise(recorded), normalise(reply)
        want_sets, got_set = lookup(index, want), response_set(p, turn)
        if want == got:
            verdict = "exact"
        elif got_set in want_sets or set(lookup(index, got)) & set(want_sets):
            verdict = "same set"
        elif want_sets:
            verdict = "in memory"
        elif not want:
            verdict = "exact" if not got else "in memory"
        else:
            verdict = "absent"
        rows.append({"asked": asked, "recorded": recorded, "reply": reply, "verdict": verdict,
                     "recorded_sets": want_sets, "port_set": got_set, "unit": turn.unit,
                     "trace": turn.trace, "affect": dict(turn.affect),
                     "recorded_affect": recorded_affect, "affect_same": affect_same})
    return version, rows


def summarise(rows):
    counts = {k: 0 for k in ("exact", "same set", "in memory", "absent")}
    for r in rows:
        counts[r["verdict"]] += 1
    with_affect = [r for r in rows if r["affect_same"] is not None]
    if with_affect:
        counts["affect same"] = f"{sum(r['affect_same'] for r in with_affect)}/{len(with_affect)}"
    return counts


def main(argv):
    names = argv[1:] or sorted(f.stem for f in TRANSCRIPTS.glob("*.txt"))
    for name in names:
        version, rows = replay(name)
        print(f"== {name} ({version})  {summarise(rows)}")
        for r in rows:
            mark = {"exact": "==", "same set": "~=", "in memory": "!=", "absent": "--"}[r["verdict"]]
            print(f"  I: {r['asked']}")
            print(f"  O: {r['recorded']}")
            print(f"  {mark} {r['reply']}    [{r['unit']} -> {r['port_set']}; recorded in {r['recorded_sets'] or '-'}; {r['trace']}]")
            if r["affect_same"] is False:
                port = " ".join(f"{k.upper()} {r['affect'].get(_AFFECT_KEYS[k], 0):.2f}" for k in r["recorded_affect"])
                rec = " ".join(f"{k.upper()} {v:.2f}" for k, v in r["recorded_affect"].items())
                print(f"     affect port: {port}   1974: {rec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
