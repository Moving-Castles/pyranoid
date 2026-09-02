"""Interactive PARRY interview.

    uv run python -m pyranoid.repl [--version STRONG|MILD|WEAK] [--trace] [--seed N]

Type a sentence ending in a period or question mark. PARRY replies in character.
End with "bye" (or Ctrl-D). --trace shows the per-turn diagnostics.
"""

from __future__ import annotations

import argparse
import sys

from pyranoid.parry import Parry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Talk to PARRY (Colby, 1972).")
    ap.add_argument("--version", default="STRONG",
                    choices=["STRONG", "MILD", "WEAK"],
                    help="paranoia level (default: STRONG)")
    ap.add_argument("--trace", action="store_true", help="show diagnostics")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed")
    args = ap.parse_args(argv)

    try:
        parry = Parry(version=args.version, seed=args.seed)
    except FileNotFoundError as e:
        print(f"could not load PARRY data: {e}", file=sys.stderr)
        return 1

    print("PARRY (Kenneth Colby, 1972) — a simulated paranoid patient.")
    print('Type a sentence; end with "bye". Ctrl-D to quit.\n')
    print("PARRY:", parry.greeting())

    while not parry.ended:
        try:
            line = input("\nYOU: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        reply = parry.respond(line)
        print("PARRY:", reply)
        if args.trace:
            t = parry.turns[-1]
            a = t.affect
            print(f"      [{t.trace} unit={t.unit} intent={t.intent} "
                  f"fear={a['fear']} anger={a['anger']} "
                  f"mistrust={a['mistrust']} hurt={a['hurt']}]")

    if parry.ended:
        print("\n(PARRY has ended the interview.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
