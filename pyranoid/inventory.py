"""Summarise the loaded PARRY image: python -m pyranoid.inventory

Prints what the data files contributed to the property-list memory and the
authentic quirks of the 1974 data that the loader surfaces rather than hides.
"""

from __future__ import annotations

import sys

from pyranoid.lisp import read_file
from pyranoid.parry import DATA_DIR, Parry


def main(argv: list[str]) -> int:
    p = Parry(seed=0)
    units = [a for a in p.plist.atoms_with("BONDVALUE")]
    sets = [a for a in p.plist.atoms_with("NORMAL")]
    sentences = sum(len(p.getprop(a, "NORMAL") or []) for a in sets)
    with_sf = [a for a in units if p.getprop(a, "SF")]
    with_fx = [a for a in units if p.getprop(a, "FX")]
    with_nn = [a for a in units if p.getprop(a, "NN")]
    print(f"data directory: {DATA_DIR}")
    print(f"  input units (#B):      {len(units)}")
    print(f"  response sets (#E):    {len(sets)}  ({sentences} sentences)")
    print(f"  semantic functions:    SF {len(with_sf)}, FX {len(with_fx)}, NN {len(with_nn)} (NN is never run)")
    print(f"  simple patterns:       {len(p.SPTABLE)}")
    print(f"  compound patterns:     {len(p.CPTABLE)}")
    print(f"  synonyms:              {len(p.plist.atoms_with('SYNONM'))}")
    print(f"  beliefs:               {len(p.plist.atoms_with('NTRUTH'))}  intentions: {len(p.INTLIST)}")
    print(f"  theorems:              {len(p.plist.atoms_with('THEOREM'))}")
    print(f"  flare sets:            {p.getprop('FLARELIST', 'SETS')}")
    print("quirks of the recovered data:")
    for e in reversed(p.ERROR_LIST or []):
        print(f"  load error: {e[0]} {e[1]}")
    dangling = [(a, p.getprop(a, "RESP")) for a in units
                if p.getprop(a, "RESP") and not p.getprop(p.getprop(a, "RESP"), "INCORE")]
    print(f"  dangling RESP references: {dangling}")
    print(f"  PDAT records defined twice (first kept, as DSKLOC read it): {p.duplicate_records}")
    missing_groups = [(f[1], f[2]) for f in read_file(DATA_DIR / "pdatb")
                      if f[3] == "IND" and not p.getprop(f[2], "INCORE")]
    print(f"  reply groups without a unit in PDAT: {missing_groups}")
    missing_patterns = sorted({v for v in p.SPTABLE.values() if v[0] == "H" and not p.getprop(v, "INCORE")
                               and not p.getprop(v, "MEQV")})
    print(f"  pattern targets in neither PDAT nor CHANGE: {missing_patterns}")
    print(f"  front-end tables missing from the source tree: {p.missing_tables}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
