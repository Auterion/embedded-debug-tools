# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# Remote GDB Access

This module provides access to remotely connected GDB and allows partial or
complete control over the GDB command prompt or the entire GDB Python API.

Currently two access methods are available:

- `emdbg.debug.remote.mi.Gdb`:
		command prompt access via the GDB/MI protocol created with
		`emdbg.debug.gdb.call_mi()`.
- `emdbg.debug.remote.rpyc.Gdb`:
		Full Python API access via RPyC created with
		`emdbg.debug.gdb.call_rpyc()`.
"""

__all__ = [
	"gdb",
	"rpyc",
	"mi",
]

from . import rpyc
from . import mi
