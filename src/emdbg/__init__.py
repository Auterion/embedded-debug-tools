# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# Embedded Debug Tools

The most important tools:

- GDB: `emdbg.debug.gdb`.
- FMU: `emdbg.bench.fmu`.
- Patches: `emdbg.patch.set`.
"""

from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("emdbg")
except PackageNotFoundError:
    __version__ = "0.0.0"


from . import analyze
from . import bench
from . import debug
from . import power
from . import serial
from . import io

from . import logger
from . import utils

# Silence warnings about path import order when calling modules directly
import sys
if not sys.warnoptions:
    import warnings
    warnings.filterwarnings('ignore', category=RuntimeWarning, module='runpy')
