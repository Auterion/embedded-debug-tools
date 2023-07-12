# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# Test Benches

A test bench uses a specific combination of pre-configured modules.
Connecting to a test bench uses the Python GDB with all scripts imported.


"""

from .fmu import debug as fmu, shell
from .skynode import debug as skynode
