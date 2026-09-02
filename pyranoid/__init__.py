"""pyranoid: Kenneth Colby's 1972 PARRY, ported routine for routine.

The package is one LISP-style image (:class:`Parry`) built from the original
source files -- the pattern front-end decompiled from ``front.lap``, the
memory and intention layers from ``pmem``, ``pmem2``, ``pmem4``, ``pmem5``,
the flare/delusion model from ``opar3`` -- running on the original data
tables and the response memory recovered from a 1974 WAITS disk image.
"""

from pyranoid.lisp import Lisp, LispError, Pair, Plist, read_file, read_forms
from pyranoid.parry import DATA_DIR, Parry, Turn

__all__ = [
    "DATA_DIR",
    "Lisp",
    "LispError",
    "Pair",
    "Parry",
    "Plist",
    "Turn",
    "read_file",
    "read_forms",
]
