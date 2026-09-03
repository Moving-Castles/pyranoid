"""`python -m pyranoid` — launch an interactive PARRY interview.

For the PDAT memory summary instead, run `python -m pyranoid.inventory [path]`.
"""

from __future__ import annotations

from pyranoid.repl import main

if __name__ == "__main__":
    raise SystemExit(main())
