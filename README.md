# pyranoid

Kenneth Colby's 1972 **PARRY** — the simulation of a paranoid mental-hospital
patient that passed a restricted Turing test and argued with ELIZA in RFC 439 —
ported to Python routine for routine from the original MLISP source, running
on the original data tables and the response memory recovered from a 1974
Stanford WAITS disk image. Everything ships inside the package.

```
READY: good afternoon. my name is doctor love. how are you?
ALL RIGHT I GUESS
READY: what do you do for a living.
I WORK AT SEARS
READY: by what.
MAYBE YOU HAVE TO WATCH OUT FOR GAMBLING
READY: tell me more.
I'VE HAD EXPERIENCE WITH CROOKS GAMBLING AT THE TRACK
READY: no, what about bookies.
A BOOKIE DIDN'T PAY ME OFF ONCE
READY: and then what happened.
I HAD AN ARGUMENT WITH THE BOOKIE WHO DID NOT PAY OFF. LATER ON I REMEMBERED HE
HAD FRIENDS IN THE UNDERWORLD AND I THOUGHT HE WOULD USE THEM TO GET EVEN WITH ME
READY: you are crazy.
THAT'S ENOUGH ABOUT THAT
```

## Run it

Python 3.10+. With [uv](https://docs.astral.sh/uv/):

```bash
uv run python -m pyranoid                 # interview (STRONG version)
uv run python -m pyranoid --trace         # with the original's per-turn diagnostics
uv run python -m pyranoid --version MILD  # STRONG | MILD | WEAK
uv run python -m pyranoid.inspect         # what the data files loaded, and their quirks
```

Or `pip install -e .` and run `parry`. As in 1974 the interviewer speaks
first; end each input with a period or question mark (one is supplied if you
forget), type `.` alone for silence, `bye` to finish. Two sentences on one
line are both processed and the second is answered, as the original did.

## What this is

PARRY was written in MLISP on a PDP-10 under WAITS. Its source survives in the
CMU AI Repository; its response memory (`PDAT`) did not, until the ELIZAGEN
team revived a 1974 WAITS disk image in 2026 and this project extracted the
files from it byte for byte. `pyranoid` is a port of the whole program:

| Module | Ported from | What it is |
|---|---|---|
| `lisp.py` | — | a small LISP 1.6 substrate: the SAIL data-file reader, list primitives, property lists, and an evaluator for the LISP that PARRY stores as data |
| `front.py` | `front.lap` (decompiled) | the linguistic front-end: tokeniser, respeller, suffix stripper, idioms and synonyms, fragmenting, simple and compound pattern matching |
| `opar.py` | `opar3` | the flare/delusion model: CHECKFLARE, DELREF, DELSTMT, FLSTMT, LEADON, FLARELEAD, CHOOSE, MISCQ/MISCS, MODIFVAR |
| `pmem.py` | `pmem` | memory linking (BEL/ENG), expression (REPLYR/EXPRESS/SELSENTENCE/SAY), anaphora (SPECFN, GO_ON, ELAB, WHO, WHAT, GET_ANAPH), stories (GET_STORY) |
| `pmem2.py` | `pmem2` | RAISE, the keyword scan, the SF routines (FLARESENT, DELNSENT, SWEARER, SILENCER, EXHAUSTER, ENDROUTINE), dates and times, SPECCONCEPT |
| `pmem4.py` | `pmem4` | PARRY2 and REACT (the turn), REACT2/REACT3, DOSF, the belief engine (READBEL/READINF/ASSERT/ADDTO/PROVE/INFERENCE) |
| `pmem5.py` | `pmem5` | CHECKINPUT, AFFECT, INFEMOTE, INTENTION/DOINTENT, the intention routines, PPARANOIA/STRONGFEEL/PARANOIA |
| `parry.py` | `dor` build script | the one core image: loads everything in the original order; `respond(line)` |

Every routine keeps its original name; every SPECIAL variable of the original
is an attribute of the `Parry` object under its original name (`FEAR`,
`AJUMP`, `DELFLAG`, `INPUTQUES`, `!OUTPUT` as `OUTPUT` …), so the port can be
read side by side with the MLISP. The data files are loaded the way the
original loaded them: `rdata` and `pdatb` are evaluated as LISP, `bel` and
`inf` go through READBEL/READINF, `PDAT` records through BEL/ENG, and the
117 semantic functions stored in `PDAT` (`SF`, plus the two `FX` input hooks)
run through the evaluator at the same points DOSF and CHECKINPUT ran them.

### Decompiling the front-end

The front-end was the one component believed lost: `front.lap` is compiled
PDP-10 LAP. It turned out to be the regular output of the LISP 1.6 compiler
and reads back cleanly (all numbers in it are octal). The real algorithm is
not the subsequence heuristic earlier reconstructions used: a fragment is
looked up as an exact pattern on the words' first five characters, or with
exactly one word dropped; flag words are removed first (NOT toggles negation,
DAD/MOM/FAMLY set a family flag, THEY is replaced by its anaphoric referent
from the memory); filler units are dropped; compound patterns combine the
fragments' units, again exactly or minus one unit. Misspellings are repaired
by deleting a letter, substituting a keyboard neighbour, or transposing.
Every routine of `front.lap` assembles to exactly the code found in the 1974
core image (below), so this is the front-end that ran.

### What the port does not have

- The 1974 `PDAT` lacks the ten paranoid-mode reply groups that `pdatb` names
  (`PANGER`, `PAFRAID`, `PACCUSE`, …). The November 1974 core image shows they
  were not in that year's `pdatb` either: they were added to the source later,
  and the `PDAT` that went with them did not survive. The code chooses them;
  the memory has no unit to say, so — as the original code dictates — the reply
  comes from REACT3's recovery: the topic's story, or the "I have already told
  you" exhaust replies. Five pattern targets are in neither `PDAT` nor
  `CHANGE`; they are targets in the 1974 binary pattern tables too, so that
  breakage is original (the 1975 FIX.DOC notes two of them).
  `python -m pyranoid.inspect` lists all of this.
- Terminal, disk and window I/O (the DIA and ERR files, the display windows,
  the learning mode that wrote new patterns) is reduced to the `Turn` record
  and the `--trace` printout; the learning-mode routines are ported but have
  no operator to answer their prompts. The original's end-of-input characters
  were carriage return and the SAIL altmode `}`; the port's are newline and
  escape.
- `RANDOM` used the run-time clock; here it is a seeded generator.

### Checked against the 1974 core image

`PARRY.DMP` (8 November 1974, recovered with the data files) is the LISP core
image of the running program, saved after every table had been loaded.
Decoding its heap — the file starts at location 74₈, an atom is a cell with
777777 in its left half, a small integer is an address counted from 577777₈ —
made it possible to check the port against the original in memory:

- Every table INIT_DICTIO puts on property lists (STARTR, STOPPR, FLAGS,
  FILLER, IRREG, SUFFIX, IDIOM, NEGATE, FAMLY, NEARBY) and every property
  that `rdata`, `pdatb`, `bel` and `inf` establish come out identical in the
  port; `DAD.PAT` and `MOM.PAT`, missing from the source tree, were read back
  out of it (seven entries each, bundled as `dad.pat` / `mom.pat`). The
  synonym table in the 5 November 1974 `ALL.PAR` binary is identical to the
  port's; the pattern tables are identical but for two simple and two
  compound patterns.
- The CMU source tree is a later revision than the image: it adds those four
  patterns, four idioms (`GOD DAMN`, `BE YOU SURE`, …), five theorems
  (IF942–IF946), the ten paranoid reply groups and a few beliefs, and changes
  the flare weights. 188 of the 247 compiled routines are the same code (all
  of `opar3`, and all of `front.lap` but the debug printer WINDOW_PRINT, which
  the image had stubbed out); the ones that differ are in `pmem`, `pmem2`,
  `pmem4`, `pmem5` and `win` — ANDTHEN, REPLYR, REPETITION, PPARANOIA,
  CHECKINPUT, AFFECT, INITPARAMS, DATE's leap years, the window code — which
  the "authentic behaviour" list below reflects. The port follows the source.
- LISP 1.6 semantics the port had assumed were confirmed from the image and
  the SAILON 28.7 manual: `PROG2` returns its second argument (up to five are
  allowed), READCH and EXPLODE return numbers for digit characters, integer
  division truncates, a SPECIAL cell that compiled code created and nothing
  assigned reads as NIL, and GET on a non-atom takes CDR first (LASTWORD,
  below). `RANDOM` is not a LISP 1.6 function: it is PARRY's own `random.lap`.

### Authentic behaviour you may take for bugs

These are in the original and are reproduced deliberately:

- ANDTHEN assigns an unset local to `!LASTIN`/`!LASTOUT`, and REPETITION
  compares a list entry with an atom, so repetition is never detected (both
  routines were rewritten after the 1974 image).
- DELSTMT, when the delusion story is used up, clears DELFLAG and immediately
  sets it again, discarding the reply it chose.
- Two `SF`s test a `SAID` property nothing sets: the 1974 REPLYR still called
  a MARK_SAID that set it, and the later source dropped the call. LASTWORD
  applies GET to an assoc pair; LISP 1.6's GET takes CDR without checking for
  an atom and walks the word's property list out of phase, so the "sensitive
  concept" and "looks" last words always come out as PROBLEMS. `(NOT FLARE)` in a theorem
  tests a belief named FLARE, not the variable. LEADON's `DELETE` of MAFIA from
  the delusion words discards its result. The `NN` properties on 13 units are
  loaded and never run (no code references them).
- The calendar has no leap years after 1973 ("previous line should be fixed on
  Feb 29, 1976"), so weekdays drift for later dates.
- The `PDAT` has one response set defined twice (`B5420`; the original located
  records through the DSKLOC index, whose binary search finds the first
  definition, so that is the one used and the second was never read) and one
  input unit whose response set is never defined (`H4897`).

## Tests

```bash
uv run --with pytest python -m pytest tests/ -q
```

78 tests: the LISP substrate, the decompiled front-end on the real tables,
the memory layer, and end-to-end interviews including the sample dialogue in
Colby's own documentation.

## Provenance

- Kenneth M. Colby et al., Stanford AI Lab, 1972–75. Source: [CMU AI
  Repository — classics/parry](https://www.cs.cmu.edu/afs/cs/project/ai-repository/ai/areas/classics/parry/)
  (preserved by Martin Frost). Public domain.
- Colby, Weber, Hilf, ["Artificial Paranoia"](https://courses.cs.umbc.edu/671/fall12/resources/colby_71.pdf),
  *Artificial Intelligence* 2 (1971); Colby, *Artificial Paranoia: A Computer
  Simulation of Paranoid Processes*, Pergamon, 1975.
- Response memory recovered from the WAITS disk images of
  [ELIZAGEN — "PARRY Parries Again"](https://sites.google.com/view/elizagen-org/blog/parry-parries-again)
  (Lars Brinkhoff, Rupert Lane) via [sailing-on-arpanet](https://github.com/larsbrinkhoff/sailing-on-arpanet)
  and [open-simh](https://github.com/open-simh/simh), using the `dart`/`cat36`
  tools from [pdp10-its-disassembler](https://github.com/larsbrinkhoff/pdp10-its-disassembler).
- [RFC 439 — PARRY Encounters the DOCTOR](https://www.rfc-editor.org/rfc/rfc439.html) (1973).

The port is MIT-licensed; Colby's source and data, bundled as
`pyranoid/data/`, are public domain.
