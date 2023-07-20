# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# Debug Tools

This module manages the configuration and lifetime of debuggers and debug probes.
In particular, it orchestrates the setup of debug probes and GDB and provides
scripting access to the GBD Python API and extends it with custom commands.

Several debug probes are supported:

- JLink via `emdbg.debug.jlink`.
- OpenOCD via `emdbg.debug.openocd`.
- CrashDebug via `emdbg.debug.crashdebug`.

The debug probes have been tested with the JLink EDU mini, JLink BASE compact,
and STLinkv3-MINIE.
"""

from . import jlink
from . import openocd
from . import gdb
from . import px4

from .backend import ProbeBackend
from .crashdebug import CrashProbeBackend
from .jlink import JLinkBackend
from .openocd import OpenOcdBackend
