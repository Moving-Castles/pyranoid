"""PARRY's belief and inference data (from bel and inf).

`bel` declares beliefs with an initial strength and a class:
  HUM/HUM2  self-beliefs (PARRY about itself: CRAZY, DUMB, LOSER, LYING, …)
  DOC       beliefs about the doctor (DMAFIA, DDHARM, DHELPFUL, DHOSTILE, …)
  INT       beliefs about the interview (INTBAD, INTHELPFUL, …)
  INN       intentions (PEXIT, PMAFIA, PHELP, PSTRONGFEEL, … ; listed in reverse
            priority order, so later entries outrank earlier ones)

`inf` holds three rule kinds (see the loaders below). This module only *loads*
and structures them; the forward-chaining engine that applies them lives in
inference.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pyranoid.data import DATA_DIR, _text


@dataclass
class Belief:
    name: str
    value: float
    cls: str                      # HUM | HUM2 | DOC | INT | INN
    complement: str | None = None  # e.g. *DCHELP
    complement_value: float = 0.0


@dataclass
class Th2Response:
    """(TH2 (BELIEF strength) unit...) — if belief >= strength, these units apply."""
    belief: str
    strength: float
    units: list


@dataclass
class Th2Group:
    """(TH2 NAME member...) — NAME is supported by any of the member beliefs."""
    name: str
    members: list


@dataclass
class Emote:
    """(EMOTE (JUMP value) belief...) — if any belief holds, set that emotion jump."""
    jump: str                     # HJUMP | FJUMP | AJUMP
    value: float
    beliefs: list


@dataclass
class InfRule:
    """(IFnnn CONSEQUENT (antecedent...)) — a forward-chaining production."""
    tag: str
    consequent: object            # belief name, or (name, strength)
    antecedents: list             # each: belief name, (NOT x), (MEASURE ...), etc.


@dataclass
class BeliefBase:
    beliefs: dict                 # name -> Belief
    th2_responses: list           # list[Th2Response]   (informational)
    th2_groups: list              # list[Th2Group]      (informational)
    emotes: list                  # list[Emote]
    rules: list                   # list[InfRule]
    th2_raw: list                 # list[(consequent, items)] — every TH2 line

    def intentions(self) -> list:
        """Intention names in priority order (bel lists them low -> high)."""
        return [b.name for b in self.beliefs.values() if b.cls == "INN"]

    def oppos(self) -> dict:
        """belief <-> its *opposite (mutual), from bel complement links."""
        out: dict = {}
        for b in self.beliefs.values():
            if b.complement:
                out[b.name] = b.complement
                out[b.complement] = b.name
        return out

    @classmethod
    def load(cls, bel_path=None, inf_path=None) -> BeliefBase:
        bel_path = Path(bel_path) if bel_path else DATA_DIR / "bel"
        inf_path = Path(inf_path) if inf_path else DATA_DIR / "inf"
        return cls(
            beliefs=_load_bel(bel_path),
            **_load_inf(inf_path),
        )


# --- a tiny s-expression reader (shared shape with pdat, kept local/simple) ---

_TOK = re.compile(r"\(|\)|[^\s()]+")


def _read_sexprs(text: str):
    """Yield each top-level s-expression as nested lists / string atoms."""
    stack: list = []
    top: list = []
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == "(":
            new: list = []
            if stack:
                stack[-1].append(new)
            stack.append(new)
        elif t == ")":
            if stack:
                done = stack.pop()
                if not stack:
                    top.append(done)
        else:
            if stack:
                stack[-1].append(t)
    return top


def _strip_comments(text: str) -> str:
    # inf/bel use ~ to end-of-line as comments
    return "\n".join(line.split("~", 1)[0] for line in text.splitlines())


def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# --- bel ---------------------------------------------------------------------

def _load_bel(path: Path) -> dict:
    text = _strip_comments(_text(path))
    out: dict = {}
    for form in _read_sexprs(text):
        if not form or not isinstance(form[0], str):
            continue
        name = form[0]
        value = _num(form[1]) if len(form) > 1 else 0.0
        cls = form[2] if len(form) > 2 and isinstance(form[2], str) else "HUM"
        comp = comp_val = None
        # optional  *COMP  compvalue  tail
        if len(form) > 4 and isinstance(form[3], str) and form[3].startswith("*"):
            comp, comp_val = form[3], _num(form[4])
        out[name] = Belief(name=name, value=value, cls=cls,
                           complement=comp, complement_value=_num(comp_val))
    return out


# --- inf ---------------------------------------------------------------------

def _load_inf(path: Path) -> dict:
    text = _strip_comments(_text(path))
    th2_responses: list = []
    th2_groups: list = []
    emotes: list = []
    rules: list = []
    th2_raw: list = []
    for form in _read_sexprs(text):
        if not form or not isinstance(form[0], str):
            continue
        head = form[0]
        if head == "TH2":
            arg = form[1]
            # consequent is a bare belief atom or (belief strength); items follow
            if isinstance(arg, list):
                consequent = (arg[0], _num(arg[1]) if len(arg) > 1 else 2.0)
            else:
                consequent = arg
            items = [x for x in form[2:] if isinstance(x, str)]
            th2_raw.append((consequent, items))
            if isinstance(arg, list):
                th2_responses.append(Th2Response(arg[0], _num(arg[1]), items))
            else:
                th2_groups.append(Th2Group(arg, items))
        elif head == "EMOTE":
            jspec = form[1]  # (JUMP value)
            if isinstance(jspec, list) and len(jspec) >= 2:
                emotes.append(Emote(jspec[0], _num(jspec[1]),
                                    [b for b in form[2:] if isinstance(b, str)]))
        elif re.match(r"^IF\d+$", head):
            consequent = form[1]
            ante = form[2] if len(form) > 2 else []
            if isinstance(ante, str):
                ante = [ante]
            rules.append(InfRule(head, consequent, ante))
    return {
        "th2_responses": th2_responses,
        "th2_groups": th2_groups,
        "emotes": emotes,
        "rules": rules,
        "th2_raw": th2_raw,
    }
