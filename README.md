# pyranoid

A faithful, runnable Python port of Kenneth Colby's 1972 **PARRY** — the
simulation of a paranoid mental-hospital patient that was the first program to
pass a restricted Turing test, and the other half of the famous 1973
"PARRY meets the DOCTOR" exchange with ELIZA (RFC 439).

This is a real port built from Colby's own source and data, not an LLM prompt or
a loose rewrite. The sentences PARRY says, the patterns it matches, and the
emotion dynamics that make it grow suspicious are Colby's. The response database
was recovered from a 1974 Stanford WAITS disk image (see
[Provenance](#provenance)) and ships inside this package, so `pyranoid` runs on
its own with nothing else to download.

```
PARRY: HELLO
YOU:   how old are you?             PARRY: TWENTY-EIGHT, HOW OLD ARE YOU?
YOU:   where do you live?           PARRY: I LIVE IN SAN JOSE
YOU:   what kind of work do you do? PARRY: I WORK IN THE STOCKROOM AT SEARS
YOU:   do you bet on the horses?    PARRY: I GAMBLE ON HORSES               [fear 8.9]
YOU:   what about the bookies?      PARRY: A BOOKIE DIDN'T PAY ME OFF ONCE   [fear 12.3]
YOU:   is the mafia after you?      PARRY: I'M NOT SURE I TRUST YOU          [fear 16.8]
YOU:   i think you need help        PARRY: PEOPLE LIKE YOU THINK YOU KNOW EVERYTHING
```

## Run it

Requires Python 3.10+. With [uv](https://docs.astral.sh/uv/):

```bash
uv run python -m pyranoid                 # interactive interview (STRONG version)
uv run python -m pyranoid --trace         # also print per-turn emotion diagnostics
uv run python -m pyranoid --version MILD  # STRONG | MILD | WEAK
```

Or with pip:

```bash
pip install -e .
parry                                     # console entry point
```

Type a sentence and press Enter. End with `bye` or Ctrl-D.

## The story

**PARRY (1972).** Colby, a psychiatrist, wrote PARRY to model paranoid thinking:
it holds a delusion (the Mafia is after him over a gambling debt), tracks four
emotions — anger, fear, mistrust, hurt — and turns defensive and then hostile as
an interviewer edges toward sensitive topics. It was written in MLISP on a PDP-10
under the Stanford WAITS operating system.

**The gap.** Colby's source survives in the CMU AI Repository, but the crucial
`PDAT` file — the memory holding the English sentences PARRY speaks — was not in
it. Without `PDAT`, the source can parse input and update emotions but has nothing
to say.

**The recovery.** In 2026 the ELIZAGEN team (Lars Brinkhoff and Rupert Lane) got
the original PARRY running again on a restored 1974 WAITS disk image. This project
booted that image in a PDP-10 emulator, used WAITS's own `DART` program to write
the PARRY data files to a virtual tape, and extracted them byte-for-byte. The
primary response database (5 Nov 1974) has 659 input units and 521 response units
— 1,279 sentences. It is bundled here as `pyranoid/data/pdatz.txt`.

## How it works

Each turn, `Parry.respond()` reconstructs PARRY's `REACT` control loop:

1. **Canonicalise** the input (`frontend.py`): expand contractions, map synonyms,
   substitute idioms, truncate words to five characters, then match against the
   simple patterns (`spats`) and reduce with compound patterns (`cpats`) to a
   semantic unit.
2. **Answer from memory** (`memory.py`): resolve a follow-up ("why?", "who?")
   against the current anaphora list, else take the matched unit's response.
3. **Run the affect model** (`model.py`) every turn: flare, delusion, and
   sensitive words set emotion "jumps"; `RAISE` applies them (saturating toward a
   ceiling of 20, with permanent sensitisation of the baselines); a high-emotion
   **intention** can pre-empt the literal answer with an evasive or hostile reply.
4. **Fall back** through a keyword scan (delusion → flare → topic story) and a
   noncommittal reply if nothing matched.
5. **Select and consume** a sentence (each said at most once per interview; a unit
   exhausts and recovers when emptied), then **decay** the emotions toward baseline.

| Module | Ported from | Role |
|---|---|---|
| `pdat.py` | recovered `pdatz` | semantic-memory loader |
| `data.py` | `dictio`, `synonm.alf`, `spats.sel`, `cpats.sel`, … | lexicon & pattern tables |
| `parry_data.py` | `rdata` | flare topics, weights, delusion sequences |
| `model.py` | `opar3`, `pmem2/4/5` | paranoid affect engine |
| `frontend.py` | `front.lap` + Colby's papers | sentence → semantic unit (reconstructed) |
| `memory.py` | `pmem`, `pdatb` | response selection & anaphora |
| `parry.py`, `repl.py` | `pmem4` REACT | control loop & interview |

All of PARRY's data lives in `pyranoid/data/` (the lexicon and pattern tables plus
the recovered response database), so the package is self-contained.

### Faithful vs. reconstructed

Faithful to the originals: the response database and every data table are the real
recovered files; the affect dynamics, flare weights, pointer chain, delusion story
sequences and version baselines are ported directly from `opar3`/`rdata`/`pmem`;
the control priority follows the `pmem4` flow.

Reconstructed: the linguistic front-end (`front.lap`) survives only as compiled
PDP-10 assembly, so its tokenise → canonicalise → match pipeline is rebuilt from
the documented algorithm and Colby's papers, running on his real pattern tables.
It maps most interview questions to the right unit; a few (for example "for a
living") mis-segment where the original's fragment analyser was subtler. These are
matcher-precision gaps, not data gaps. The data itself also has authentic quirks
(one duplicate response id, one dangling reference), which the loader surfaces
rather than hides.

## Tests

```bash
uv run --with pytest python -m pytest tests/ -q
```

51 tests, all running against the bundled data.

## Provenance

The recovery tooling (the PDP-10 emulator setup, the WAITS console drivers, and
the byte-for-byte extraction) is **not** included here — this repository is just
the port and the data it needs. The original MLISP source and the emulator
recovery are documented at the sources below.

- **PARRY** — Kenneth M. Colby et al., Stanford AI Lab, 1972. The original source
  is public domain per the CMU AI Repository.
- Colby, K. M., Weber, S., Hilf, F. D. "Artificial paranoia." *Artificial
  Intelligence* 2(1), 1971.
- Colby, K. M. *Artificial Paranoia: A Computer Simulation of Paranoid Processes.*
  Pergamon Press, 1975.
- Original source: [CMU AI Repository — classics/parry](https://www.cs.cmu.edu/afs/cs/project/ai-repository/ai/areas/classics/parry/)
  (preserved by Martin Frost, Stanford).
- WAITS revival & disk images: [ELIZAGEN — "PARRY Parries Again"](https://sites.google.com/view/elizagen-org/blog/parry-parries-again)
  (Lars Brinkhoff & Rupert Lane), from [Bruce Baumgart's saildart archive](https://www.saildart.org/).
- WAITS disk images: [larsbrinkhoff/sailing-on-arpanet](https://github.com/larsbrinkhoff/sailing-on-arpanet);
  emulator [rcornwell/sims](https://github.com/rcornwell/sims) / [open-simh](https://github.com/open-simh/simh).
- PDP-10 tooling (`dart`, `cat36`): [larsbrinkhoff/pdp10-its-disassembler](https://github.com/larsbrinkhoff/pdp10-its-disassembler).
- [RFC 439 — PARRY Encounters the DOCTOR](https://www.rfc-editor.org/rfc/rfc439.html) (Vint Cerf, 1973).

## License

This port is MIT-licensed (see `LICENSE`). Colby's original PARRY source and data,
included here as `pyranoid/data/`, are public domain.
