"""Interview PARRY at a terminal.

    uv run python -m pyranoid [--version STRONG|MILD|WEAK] [--trace] [--seed N]
                              [--suppress] [--experiment]

As in the original session, the interviewer speaks first.  End each input
with a period or question mark (one is supplied if missing), type ``.`` alone
for silence, and ``bye`` to finish.  ``--trace`` prints, after each reply,
the diagnostics the original wrote to its DIA file (the matched unit, its
bond, the memory's performance code, new beliefs, the intention) and the
emotion variables that TRACEV printed; ``--suppress`` hides the non-verbal
gestures such as ``(EXITS)``.
"""

from __future__ import annotations

import argparse
import sys

from pyranoid.lisp import show
from pyranoid.parry import Parry

_INSTRUCTIONS = """
END INPUT WITH A PERIOD OR QUESTION MARK,
   FOLLOWED BY CARRIAGE RETURN.
TO INDICATE SILENCE, TYPE   .
   WHEN FINISHED, TYPE   BYE.
USE PERIODS ONLY AT THE ENDS OF SENTENCES,
   NOT IN ABBREVIATIONS.
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Interview PARRY (Colby, 1972).")
    ap.add_argument("--version", default="STRONG", choices=["STRONG", "MILD", "WEAK"],
                    help="paranoia version (default: STRONG)")
    ap.add_argument("--trace", action="store_true", help="show the per-turn diagnostics")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed")
    ap.add_argument("--suppress", action="store_true", help="suppress the non-verbal feature")
    ap.add_argument("--experiment", action="store_true",
                    help="the SEVEN experiment: shame +5 at input 7, -5 at input 17")
    args = ap.parse_args(argv)

    try:
        parry = Parry(version=args.version, seed=args.seed, suppress=args.suppress, trace=args.trace)
    except FileNotFoundError as e:
        print(f"could not load PARRY data: {e}", file=sys.stderr)
        return 1
    if args.experiment:
        parry.EXPERIMENT = "SEVEN"

    print("PARRY (Kenneth Colby, 1972) -- a simulated paranoid patient.")
    print(_INSTRUCTIONS)
    while not parry.ended:
        try:
            line = input("READY: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        reply = parry.respond(line)
        print(reply)
        if args.trace:
            t = parry.turns[-1]
            print(f"      ({show(t.unit)} {show(t.bond)} {show(t.trace)} "
                  f"{show(t.new_beliefs)} {show(t.intent)})")
            print(f"      FEAR = {parry.numed(parry.FEAR)}   ANGER = {parry.numed(parry.ANGER)}"
                  f"   SHAME = {parry.numed(parry.HURT)}   MISTRUST = {parry.numed(parry.MISTRUST)}")
            for label, value in t.log:
                if label in ("Preprocess:", "New beliefs:", "Inferences succeeded:",
                             "Intentions:", "Action:", "Emotions:"):
                    print(f"      {label:24}{show(value)}")
        print()

    if parry.ended:
        print("(PARRY has ended the interview.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
