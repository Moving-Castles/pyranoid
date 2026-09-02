"""Summarise a decoded PDAT file: python -m pyranoid.inspect [path-to-pdat.txt]

Defaults to the recovered PDATZ. Prints counts, data quirks, and a few sample
belief -> response mappings so you can eyeball that the load worked.
"""

from __future__ import annotations

import sys
from pathlib import Path

from pyranoid.data import DATA_DIR
from pyranoid.pdat import load_pdat

DEFAULT = DATA_DIR / "pdatz.txt"


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    if not path.exists():
        print(f"no such file: {path}", file=sys.stderr)
        return 1
    mem = load_pdat(path)
    print(f"loaded {path.name}")
    print(f"  belief units (#B): {len(mem.beliefs)}")
    print(f"  response units (#E): {len(mem.responses)}")
    print(f"  duplicate ids: {mem.duplicate_names or 'none'}")
    print(f"  dangling RESP refs: {mem.dangling_responses() or 'none'}")
    total = sum(len(r.normal) for r in mem.responses.values())
    print(f"  candidate response sentences: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
