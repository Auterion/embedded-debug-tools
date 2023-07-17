# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from pathlib import Path

def read_gdb_log(logfile: Path) -> str:
    """
    Reads a GDB log file and converts a GDB/MI format back into a normal string.
    """
    text = Path(logfile).read_text()
    if '\n~"' in text:
        lines = text.splitlines()
        text = "\n".join(l[2:-1].encode("latin-1").decode('unicode_escape').strip() for l in lines if l.startswith('~"'))
    return text
