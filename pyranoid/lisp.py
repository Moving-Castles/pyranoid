"""A minimal Stanford LISP 1.6 substrate for PARRY.

PARRY is a property-list program: its memory, lexicon, beliefs and flare
tables all live as properties on atoms (``PUTPROP``/``GET``), its data files
are LISP forms evaluated at load time (``rdata``, ``pdatb``), and its semantic
functions (the ``SF``/``FX`` properties in PDAT, the antecedents in ``inf``)
are s-expressions handed to ``EVAL`` at run time.  This module supplies just
enough of that world for the port to run the original code paths unchanged:

* a reader for the SAIL LISP data syntax (``@`` quote, ``~`` comments,
  ``[`` ``]`` super-parentheses, ``/`` escapes, dotted pairs, the ``λ``/``α``
  unit-id glyphs of the recovered PDAT),
* LISP list primitives over Python lists / :class:`Pair` (NIL is ``None``),
* a property-list store keyed by atom,
* an evaluator for the special forms and builtins the data actually uses,
  delegating variables and named functions to a host object (the ``Parry``
  instance) so ``(SETQ AJUMP 0.5)`` moves the real affect variable and
  ``(CHOOSE @GUARD)`` calls the real CHOOSE.

Dynamic scope, ``ERRSET`` error trapping, and PROG2-returns-its-second-value
semantics are reproduced because the original code depends on them.
"""

from __future__ import annotations

import re
from typing import ClassVar

NIL = None
T = True


class LispError(Exception):
    """A run-time LISP error; trapped by ERRSET where the original traps it."""


# ---------------------------------------------------------------------------
# Data: atoms are str / int / float / True(T) / None(NIL); lists are Python
# lists (never empty: the empty list is NIL); dotted pairs are Pair.
# ---------------------------------------------------------------------------


class Pair:
    """A dotted pair ``(car . cdr)`` whose cdr is not a list."""

    __slots__ = ("car", "cdr")

    def __init__(self, car, cdr):
        self.car = car
        self.cdr = cdr

    def __eq__(self, other):
        return isinstance(other, Pair) and equal(self.car, other.car) and equal(self.cdr, other.cdr)

    def __hash__(self):
        return hash((repr(self.car), repr(self.cdr)))

    def __repr__(self):
        return f"({show(self.car)} . {show(self.cdr)})"


def is_nil(x) -> bool:
    return x is None or x is False or (isinstance(x, list) and not x)


def truthy(x) -> bool:
    return not is_nil(x)


def atom(x) -> bool:
    return not isinstance(x, (list, Pair)) or is_nil(x)


def numberp(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def car(x):
    if is_nil(x):
        return NIL
    if isinstance(x, Pair):
        return x.car
    if isinstance(x, list):
        return x[0]
    raise LispError(f"CAR of atom {show(x)}")


def cdr(x):
    if is_nil(x):
        return NIL
    if isinstance(x, Pair):
        return x.cdr
    if isinstance(x, list):
        return x[1:] if len(x) > 1 else NIL
    raise LispError(f"CDR of atom {show(x)}")


def caar(x):
    return car(car(x))


def cadr(x):
    return car(cdr(x))


def cddr(x):
    return cdr(cdr(x))


def cadar(x):
    return car(cdr(car(x)))


def caddr(x):
    return car(cdr(cdr(x)))


def cons(a, d):
    if is_nil(d):
        return [a]
    if isinstance(d, list):
        return [a, *d]
    return Pair(a, d)


def ncons(a):
    return [a]


def xcons(d, a):
    return cons(a, d)


def to_list(x) -> list:
    """A Python list view of a LISP list (NIL -> [])."""
    if is_nil(x):
        return []
    if isinstance(x, list):
        return x
    raise LispError(f"not a list: {show(x)}")


def lst(*items):
    return list(items) if items else NIL


def append(a, b):
    a, b = to_list(a), to_list(b)
    out = a + b
    return out or NIL


def reverse(x):
    out = list(reversed(to_list(x)))
    return out or NIL


def length(x) -> int:
    return len(to_list(x))


def last(x):
    """LAST: the last cons cell, so ``car(last(x))`` is the last element."""
    xs = to_list(x)
    return [xs[-1]] if xs else NIL


def nth(x, n: int):
    """1-based ``L[N]`` of MLISP."""
    xs = to_list(x)
    return xs[n - 1] if 1 <= n <= len(xs) else NIL


def equal(a, b) -> bool:
    if is_nil(a) and is_nil(b):
        return True
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
    if isinstance(a, Pair) and isinstance(b, Pair):
        return equal(a.car, b.car) and equal(a.cdr, b.cdr)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if numberp(a) and numberp(b):
        return a == b
    return type(a) is type(b) and a == b


def eq(a, b) -> bool:
    """EQ: identity for atoms (numbers compare by value, as small fixnums did)."""
    if is_nil(a) and is_nil(b):
        return True
    if isinstance(a, (list, Pair)) or isinstance(b, (list, Pair)):
        return a is b
    return equal(a, b)


def memq(x, l):
    """MEMQ: the tail of ``l`` starting at ``x``, or NIL."""
    xs = to_list(l)
    for i, item in enumerate(xs):
        if eq(x, item):
            return xs[i:]
    return NIL


def member(x, l):
    xs = to_list(l)
    for i, item in enumerate(xs):
        if equal(x, item):
            return xs[i:]
    return NIL


def assoc(key, alist):
    """ASSOC over a list of pairs (dotted or proper); returns the pair."""
    for item in to_list(alist):
        if isinstance(item, Pair):
            if equal(item.car, key):
                return item
        elif isinstance(item, list) and item and equal(item[0], key):
            return item
    return NIL


def prelist(l, n: int):
    """PRELIST: the first ``n`` elements."""
    xs = to_list(l)[: max(int(n), 0)]
    return xs or NIL


def suflist(l, n: int):
    """SUFLIST: the list after the first ``n`` elements."""
    xs = to_list(l)[max(int(n), 0):]
    return xs or NIL


def deleten(l, n: int):
    """DELETEN (pmem): the list minus its ``n``th (1-based) element."""
    xs = list(to_list(l))
    if 1 <= n <= len(xs):
        del xs[n - 1]
    return xs or NIL


def delete(x, l):
    """DELETE (opar3): remove the first element EQUAL to ``x``."""
    xs = list(to_list(l))
    for i, item in enumerate(xs):
        if equal(item, x):
            del xs[i]
            break
    return xs or NIL


def subst(new, old, form):
    if equal(form, old):
        return new
    if isinstance(form, list):
        return [subst(new, old, f) for f in form]
    if isinstance(form, Pair):
        return Pair(subst(new, old, form.car), subst(new, old, form.cdr))
    return form


def explode(x):
    """EXPLODE: the characters of an atom's print name (digits as numbers)."""
    out = []
    for ch in pname(x):
        out.append(int(ch) if ch.isdigit() else ch)
    return out or NIL


def readlist(chars):
    """READLIST: intern the atom spelled by a list of characters."""
    return intern("".join(pname(c) for c in to_list(chars)))


def intern(name: str):
    if name == "NIL":
        return NIL
    if name == "T":
        return T
    n = _number(name)
    return name if n is None else n


def pname(x) -> str:
    if x is None:
        return "NIL"
    if x is True:
        return "T"
    if isinstance(x, float) and x == int(x) and "e" not in repr(x):
        return repr(x)
    return str(x)


def chrval(x) -> int:
    """CHRVAL: the ASCII code of an atom's first character."""
    s = pname(x)
    return ord(s[0]) if s else 0


def lambdaname(x) -> bool:
    """LAMBDANAME: is ``x`` a ^H unit id (``H`` + digits in this port)?"""
    return isinstance(x, str) and len(x) == 5 and x[0] == "H" and x[1:].isdigit()


def alphaname(x) -> bool:
    """ALPHANAME: is ``x`` a ^B sentence-set id (``B`` + digits)?"""
    return isinstance(x, str) and len(x) == 5 and x[0] == "B" and x[1:].isdigit()


def show(x) -> str:
    """Print a form the way LISP would (without the ^H/^B control glyphs)."""
    if isinstance(x, list):
        return "(" + " ".join(show(i) for i in x) + ")"
    if isinstance(x, Pair):
        return repr(x)
    return pname(x)


def words(x) -> str:
    """Render a sentence (list of atoms / non-verbal lists) as text."""
    if is_nil(x):
        return ""
    if isinstance(x, str):
        return x
    parts = []
    for item in to_list(x):
        if isinstance(item, list):
            parts.append("(" + words(item) + ")")
        else:
            parts.append(pname(item))
    return " ".join(parts)


_NUMBER = re.compile(r"^-?\d+(\.\d*)?$|^-?\.\d+$")


def _number(tok: str):
    if not _NUMBER.match(tok):
        return None
    return float(tok) if "." in tok else int(tok)


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------

_WS = " \t\r\n\f\v"
_DELIM = _WS + "()[]"


def decode_bytes(raw: bytes) -> str:
    """Decode a SAIL data file: map the ^H/^B unit-id control bytes to H/B."""
    raw = raw.replace(b"\x08", b"H").replace(b"\x02", b"B")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def normalise_glyphs(text: str) -> str:
    """Map the recovered PDAT's λ/α unit-id glyphs to the H/B spelling."""
    return text.replace("λ", "H").replace("α", "B")


class Reader:
    """Reads LISP forms from text in the dialect of PARRY's data files."""

    def __init__(self, text: str):
        self.s = text
        self.i = 0
        self.n = len(text)

    def _skip(self) -> None:
        while self.i < self.n:
            c = self.s[self.i]
            if c in _WS:
                self.i += 1
            elif c == "~":  # comment to end of line
                while self.i < self.n and self.s[self.i] != "\n":
                    self.i += 1
            else:
                break

    def _atom(self):
        out: list[str] = []
        while self.i < self.n:
            c = self.s[self.i]
            if c in _DELIM:
                break
            if c == "/" and self.i + 1 < self.n:  # SAIL escape
                out.append(self.s[self.i + 1])
                self.i += 2
                continue
            if c == ".":
                prev = out[-1] if out else ""
                nxt = self.s[self.i + 1] if self.i + 1 < self.n else ""
                if prev.isdigit() and nxt.isdigit():  # decimal point
                    out.append(c)
                    self.i += 1
                    continue
                if out:
                    break  # dotted-pair separator glued to the car (THEY.MAFIA)
            out.append(c)
            self.i += 1
        return intern("".join(out))

    def read(self, depth: int = 0):
        """Read one form; returns EOF at end of input."""
        while True:
            self._skip()
            if self.i >= self.n:
                return EOF
            c = self.s[self.i]
            if c == "(":
                self.i += 1
                return self._list(")", depth + 1)
            if c == "[":
                self.i += 1
                return self._list("]", depth + 1)
            if c in ")]":
                if depth == 0:
                    self.i += 1  # stray closer at top level (rdata's ]]]]]): ignore
                    continue
                return _CLOSE
            if c == "@":
                self.i += 1
                form = self.read(depth)
                return ["QUOTE", form]
            if c == ".":
                self.i += 1
                return _DOT
            return self._atom()

    def _list(self, closer: str, depth: int):
        items: list = []
        while True:
            self._skip()
            if self.i >= self.n:
                raise LispError("unterminated list")
            c = self.s[self.i]
            if c == ")":
                self.i += 1
                if closer == ")":
                    return items or NIL
                return items or NIL  # a ")" closing inside [ ]: ordinary close
            if c == "]":
                if closer == "]":
                    self.i += 1
                    return items or NIL
                # super-paren: close this ( and leave ] for the enclosing [
                return items or NIL
            form = self.read(depth)
            if form is _DOT:
                cdr_ = self.read(depth)
                self._skip()
                if self.i < self.n and self.s[self.i] in ")]" and (self.s[self.i] == ")" or closer == "]"):
                    self.i += 1
                if is_nil(cdr_):
                    return items or NIL
                if isinstance(cdr_, list):
                    return items + cdr_
                return Pair(items[0] if len(items) == 1 else items, cdr_)
            if form is _CLOSE:
                continue
            items.append(form)


EOF = object()
_CLOSE = object()
_DOT = object()


def read_forms(text: str):
    r = Reader(text)
    while True:
        form = r.read()
        if form is EOF:
            return
        yield form


def read_file(path) -> list:
    """Read every form of a data file (decoding the control-byte unit ids)."""
    from pathlib import Path

    text = decode_bytes(Path(path).read_bytes())
    return list(read_forms(normalise_glyphs(text)))


# ---------------------------------------------------------------------------
# Property lists
# ---------------------------------------------------------------------------


def _key(atom_):
    if atom_ is None:
        return "NIL"
    if atom_ is True:
        return "T"
    return atom_


class Plist:
    """The property lists of every atom (GET / PUTPROP / DEFPROP)."""

    def __init__(self):
        self.props: dict = {}

    def get(self, atom_, prop):
        if isinstance(atom_, (list, Pair)):
            return self._get_of_cons(atom_, prop)
        return self.props.get(_key(atom_), {}).get(prop)

    def _get_of_cons(self, x, prop):
        """GET applied to a cons.  LISP 1.6's GET (disassembled from the 1974
        core image) takes CDR of its argument without testing for an atom and
        walks the result as (indicator value ...) pairs with EQ.  On a list
        that is a property-list search of its tail.  On an assoc pair
        (KEY . WORD) it walks the word atom's cell and property list out of
        phase: the values are compared with the indicator and the element
        after a match -- the next indicator, or PNAME -- is returned, which in
        practice means NIL.  LASTWORD relies on this."""
        rest = x.cdr if isinstance(x, Pair) else x[1:]
        if rest is None or rest == []:
            return NIL
        if isinstance(rest, list):
            for i in range(0, len(rest) - 1, 2):
                if rest[i] == prop:
                    return rest[i + 1]
            return NIL
        if isinstance(rest, Pair):
            return NIL
        pairs = list(self.props.get(_key(rest), {}).items())[::-1]  # PUTPROP pushes on the front
        for k, (_ind, val) in enumerate(pairs):
            if isinstance(val, str) and val == prop:
                return pairs[k + 1][0] if k + 1 < len(pairs) else "PNAME"
        return NIL

    def put(self, atom_, value, prop):
        if isinstance(atom_, (list, Pair)):
            # The original's READINF does PUTPROP on a list for two TH2 lines
            # whose "item" is an antecedent form; LISP 1.6 clobbered the cons.
            # Nothing ever reads it back, so it is a no-op here.
            return value
        self.props.setdefault(_key(atom_), {})[prop] = value
        return value

    def atoms_with(self, prop):
        return [a for a, ps in self.props.items() if prop in ps]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class _Return(Exception):
    def __init__(self, value):
        self.value = value


class Lisp:
    """EVAL for the forms PARRY stores as data.

    Variables and non-builtin functions resolve through ``host``:
    ``host.lisp_get(name)`` / ``host.lisp_set(name, value)`` for the SPECIAL
    variables, and ``host.lisp_fn(name)`` for named routines (CHOOSE, BL,
    ADDTO, the SF/intent routines, ...).
    """

    def __init__(self, host, plist: Plist):
        self.host = host
        self.plist = plist

    # -- entry points -------------------------------------------------------

    def eval(self, form, env: dict | None = None):
        if env is None:
            env = {}
        if form is None or form is True or numberp(form):
            return form
        if isinstance(form, str):
            if form in env:
                return env[form]
            return self.host.lisp_get(form)
        if isinstance(form, Pair):
            raise LispError(f"cannot evaluate dotted pair {form!r}")
        head = form[0]
        args = form[1:]
        if isinstance(head, list):
            if head and head[0] == "LAMBDA":
                return self._apply_lambda(head, [self.eval(a, env) for a in args], env)
            raise LispError(f"bad function {show(head)}")
        special = self._SPECIAL.get(head)
        if special is not None:
            return special(self, args, env)
        return self.apply(head, [self.eval(a, env) for a in args], env)

    def apply(self, name, args: list, env: dict | None = None):
        fn = self._BUILTIN.get(name)
        if fn is not None:
            return fn(self, *args)
        host_fn = self.host.lisp_fn(name)
        if host_fn is None:
            raise LispError(f"undefined function {name}")
        return host_fn(*args)

    def _apply_lambda(self, lam, args, env):
        params = to_list(lam[1])
        body = lam[2:]
        inner = dict(env)
        for p, a in zip(params, args):
            inner[p] = a
        result = NIL
        for f in body:
            result = self.eval(f, inner)
        return result

    # -- special forms ------------------------------------------------------

    def _sf_quote(self, args, env):
        return args[0] if args else NIL

    def _sf_cond(self, args, env):
        for clause in args:
            clause = to_list(clause)
            if not clause:
                continue
            test = self.eval(clause[0], env)
            if truthy(test):
                result = test
                for f in clause[1:]:
                    result = self.eval(f, env)
                return result
        return NIL

    def _sf_and(self, args, env):
        result = T
        for a in args:
            result = self.eval(a, env)
            if is_nil(result):
                return NIL
        return result

    def _sf_or(self, args, env):
        for a in args:
            result = self.eval(a, env)
            if truthy(result):
                return result
        return NIL

    def _sf_prog2(self, args, env):
        # LISP 1.6 PROG2: evaluate every argument, return the second one.
        vals = [self.eval(a, env) for a in args]
        return vals[1] if len(vals) > 1 else (vals[0] if vals else NIL)

    def _sf_progn(self, args, env):
        result = NIL
        for a in args:
            result = self.eval(a, env)
        return result

    def _sf_prog(self, args, env):
        inner = dict(env)
        for v in to_list(args[0]) if args else []:
            inner[v] = NIL
        try:
            for f in args[1:]:
                if isinstance(f, str):
                    continue  # a PROG label
                self.eval(f, inner)
        except _Return as r:
            return r.value
        return NIL

    def _sf_return(self, args, env):
        raise _Return(self.eval(args[0], env) if args else NIL)

    def _sf_setq(self, args, env):
        result = NIL
        for name, valform in zip(args[0::2], args[1::2]):
            result = self.eval(valform, env)
            if name in env:
                env[name] = result
            else:
                self.host.lisp_set(name, result)
        return result

    def _sf_set(self, args, env):
        name = self.eval(args[0], env)
        value = self.eval(args[1], env)
        if name in env:
            env[name] = value
        else:
            self.host.lisp_set(name, value)
        return value

    def _sf_function(self, args, env):
        return args[0]

    def _sf_defprop(self, args, env):
        a, v, p = args[0], args[1], args[2]
        self.plist.put(a, v, p)
        return a

    def _sf_mapcar(self, args, env):
        fn = self.eval(args[0], env)
        items = to_list(self.eval(args[1], env))
        out = []
        for item in items:
            if isinstance(fn, list) and fn and fn[0] == "LAMBDA":
                out.append(self._apply_lambda(fn, [item], env))
            else:
                out.append(self.apply(fn, [item], env))
        return out or NIL

    def _sf_lambda(self, args, env):
        return ["LAMBDA", *args]

    _SPECIAL: ClassVar[dict] = {
        "QUOTE": _sf_quote,
        "COND": _sf_cond,
        "AND": _sf_and,
        "OR": _sf_or,
        "PROG2": _sf_prog2,
        "PROGN": _sf_progn,
        "PROG": _sf_prog,
        "RETURN": _sf_return,
        "SETQ": _sf_setq,
        "SET": _sf_set,
        "FUNCTION": _sf_function,
        "DEFPROP": _sf_defprop,
        "MAPCAR": _sf_mapcar,
        "LAMBDA": _sf_lambda,
    }

    # -- builtins -----------------------------------------------------------

    def _b_get(self, a, p):
        return self.plist.get(a, p)

    def _b_putprop(self, a, v, p):
        return self.plist.put(a, v, p)

    def _b_eval(self, form):
        return self.eval(form)

    def _b_greaterp(self, a, b):
        return T if _num(a) > _num(b) else NIL

    def _b_lessp(self, a, b):
        return T if _num(a) < _num(b) else NIL

    def _b_gequal(self, a, b):
        return T if _num(a) >= _num(b) else NIL

    def _b_lequal(self, a, b):
        return T if _num(a) <= _num(b) else NIL

    def _b_plus(self, *xs):
        return sum(_num(x) for x in xs)

    def _b_difference(self, a, b):
        return _num(a) - _num(b)

    def _b_times(self, *xs):
        out = 1
        for x in xs:
            out *= _num(x)
        return out

    def _b_quo(self, a, b):
        """*QUO: integer division for fixnums (as in LISP 1.6)."""
        a, b = _num(a), _num(b)
        if isinstance(a, int) and isinstance(b, int):
            if b == 0:
                raise LispError("division by zero")
            return int(a / b)
        return a / b

    def _b_print(self, x):
        self.host.lisp_print(x)
        return x

    _BUILTIN: ClassVar[dict] = {
        "CAR": lambda self, x: car(x),
        "CDR": lambda self, x: cdr(x),
        "CAAR": lambda self, x: caar(x),
        "CADR": lambda self, x: cadr(x),
        "CDDR": lambda self, x: cddr(x),
        "CADAR": lambda self, x: cadar(x),
        "CADDR": lambda self, x: caddr(x),
        "CARN": lambda self, x: x if atom(x) else car(x),
        "CONS": lambda self, a, d: cons(a, d),
        "NCONS": lambda self, a: ncons(a),
        "XCONS": lambda self, d, a: xcons(d, a),
        "LIST": lambda self, *xs: lst(*xs),
        "APPEND": lambda self, a, b: append(a, b),
        "REVERSE": lambda self, x: reverse(x),
        "LENGTH": lambda self, x: length(x),
        "LAST": lambda self, x: last(x),
        "MEMQ": lambda self, x, l: memq(x, l),
        "MEMBER": lambda self, x, l: member(x, l),
        "ASSOC": lambda self, k, l: assoc(k, l),
        "EQ": lambda self, a, b: T if eq(a, b) else NIL,
        "EQUAL": lambda self, a, b: T if equal(a, b) else NIL,
        "NEQ": lambda self, a, b: NIL if eq(a, b) else T,
        "NEQUAL": lambda self, a, b: NIL if equal(a, b) else T,
        "NULL": lambda self, x: T if is_nil(x) else NIL,
        "NOT": lambda self, x: T if is_nil(x) else NIL,
        "ATOM": lambda self, x: T if atom(x) else NIL,
        "NUMBERP": lambda self, x: T if numberp(x) else NIL,
        "ZERONIL": lambda self, x: 0 if is_nil(x) else x,
        "GET": _b_get,
        "PUTPROP": _b_putprop,
        "EVAL": _b_eval,
        "GREATERP": _b_greaterp,
        "LESSP": _b_lessp,
        "GEQUAL": _b_gequal,
        "LEQUAL": _b_lequal,
        "PLUS": _b_plus,
        "DIFFERENCE": _b_difference,
        "TIMES": _b_times,
        "*QUO": _b_quo,
        "QUOTIENT": _b_quo,
        "ADD1": lambda self, x: _num(x) + 1,
        "SUB1": lambda self, x: _num(x) - 1,
        "MAX": lambda self, a, b: a if _num(a) >= _num(b) else b,
        "MIN": lambda self, a, b: a if _num(a) <= _num(b) else b,
        "PRELIST": lambda self, l, n: prelist(l, n),
        "SUFLIST": lambda self, l, n: suflist(l, n),
        "SUBST": lambda self, new, old, form: subst(new, old, form),
        "DELETE": lambda self, x, l: delete(x, l),
        "LAMBDANAME": lambda self, x: T if lambdaname(x) else NIL,
        "EXPLODE": lambda self, x: explode(x),
        "READLIST": lambda self, x: readlist(x),
        "CHRVAL": lambda self, x: chrval(x),
        "PRINT": _b_print,
        "TERPRI": lambda self, *x: NIL,
        "PRINTSTR": lambda self, *x: NIL,
    }


def _num(x):
    if numberp(x):
        return x
    if is_nil(x):
        return 0
    raise LispError(f"non-numeric argument {show(x)}")
