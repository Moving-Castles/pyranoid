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
   strip suffixes to a known root, substitute idioms, segment into fragments at
   startr/stoppr boundaries, then match against the simple patterns (`spats`),
   reduce with compound patterns (`cpats`), and flip on negation (`negate.pat`) to
   a semantic unit.
2. **Answer from memory** (`memory.py`): resolve a follow-up ("why?", "who?")
   against the current anaphora list (with `!ALLANAPHS` synonyms), else the
   matched unit's response.
3. **Infer** (`inference.py`): the matched unit's `TH2` hooks assert beliefs about
   the doctor (hostile, harmful, insulting, mafia-connected) and about the self
   (crazy, dumb, loser, lying); asserting a belief fires its `EMOTE` rules, arming
   the HURT/FEAR/ANGER jumps; `IF`-theorems forward-chain to more beliefs and to
   intention scores.
4. **Affect** (`model.py`, `parry.py`): `RAISE` applies the jumps (saturating
   toward 20, with permanent sensitisation); on high emotion an **intention**
   (`PPARANOIA`, `PSTRONGFEEL`, `PEXIT2`) is forced, and paranoia projects the
   self-shame onto distrust of the doctor.
5. **Do-intent**: the highest-priority intention above threshold drives the reply,
   routed by the matched unit's `CLASS`, pre-empting the literal answer. Otherwise
   fall back through the keyword scan and a noncommittal reply.
6. **Select and consume** a sentence (each said at most once per interview; a unit
   exhausts and recovers when emptied), then **decay** the emotions toward baseline.

| Module | Ported from | Role |
|---|---|---|
| `pdat.py` | recovered `pdatz` | semantic-memory loader |
| `data.py` | `dictio`, `synonm.alf`, `spats.sel`, `cpats.sel`, `suffix`, `negate.pat`, … | lexicon & pattern tables |
| `parry_data.py` | `rdata` | flare topics, weights, delusion sequences |
| `model.py` | `opar3`, `pmem2/4/5` | paranoid affect engine (RAISE, decay, flares, delusion) |
| `beliefs.py` | `bel`, `inf` | belief table and TH2/EMOTE/IF rule loader |
| `inference.py` | `pmem4/5` | the "doctor model": forward-chaining beliefs, EMOTE jumps, intentions |
| `frontend.py` | `front.lap` + Colby's papers | sentence → semantic unit (reconstructed) |
| `memory.py` | `pmem`, `pdatb` | response selection & anaphora |
| `parry.py`, `repl.py` | `pmem4` REACT | control loop (INFERENCE→AFFECT→DOINTENT) & interview |

All of PARRY's data lives in `pyranoid/data/` (the lexicon and pattern tables plus
the recovered response database), so the package is self-contained.

### Faithful vs. reconstructed

**Faithful to the originals** (ported directly, verified against source): the
response database and every data table are the real recovered files; the affect
engine (`RAISE`, `MODIFVAR`, the saturating updates and cross-coupling constants,
version baselines); the flare weights, pointer chain, and delusion story
sequences; the belief table and the TH2/EMOTE/IF inference rules; the forward-
chaining `PROVE`, `ASSERT2`/`ADDTO`/`INFEMOTE` semantics and the `INFERENCE →
AFFECT → DOINTENT` control flow; response cycling and exhaustion.

**Reconstructed** (from the documented algorithm and Colby's papers, running on
his real data): the linguistic front-end (`front.lap`) survives only as compiled
PDP-10 assembly, so the tokenise → canonicalise → segment → match pipeline is
rebuilt. It maps most interview questions to the right unit; a few mis-segment
where the original's analyser was subtler.

**Simplified / not yet ported** (honest remaining gaps): the proactive delusion
lead-in (`PHELP`→`FLARELEAD`) is passive, so PARRY steers toward its Mafia story
less than the original; a few intent routines (`PONTOP`, `PGETBACK`, `PSUFFER`)
and `CHECKINPUT`'s gibberish/misspelling detection are stubs; the statistical
doctor-model rules that read conversation counters (`NEWTOPICNO`, `SPECFNRA`) are
inert because those counters aren't fully tracked; a handful of front-end tables
(`multi`, `nearby.key` respeller, `famly`/`same`/`filler`) are loaded but unused.

The data itself has authentic quirks (one duplicate response id, one dangling
reference) that the loader surfaces rather than hides.

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
- Colby, K. M., Weber, S., Hilf, F. D. ["Artificial Paranoia."](https://courses.cs.umbc.edu/671/fall12/resources/colby_71.pdf)
  *Artificial Intelligence* 2 (1971), 1–25. The paper describing PARRY's model.
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
