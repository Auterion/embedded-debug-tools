# Copyright (c) 2020-2022, Niklas Hauser
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: crashdebug.md
"""

from __future__ import annotations
import os, platform
from pathlib import Path
from .backend import ProbeBackend

class CrashProbeBackend(ProbeBackend):
    """
    CrashDebug specific debug backend implementation. Note that this
    implementation only pretends to connect to the microcontroller so that GDB
    can access the device's memory.

    .. warning::  You cannot execute code using this backend.
        You can only look around the device's memories at least as far as they
        have been saved by the coredump command.
    """
    def __init__(self, coredump: Path):
        super().__init__()
        self.coredump = coredump
        self.binary = "CrashDebug"
        if "Windows" in platform.platform():
            self.binary = "CrashDebug.exe"
        self.binary = os.environ.get("PX4_CRASHDEBUG_BINARY", self.binary)

    def init(self, elf: Path):
        return ["set target-charset ASCII",
                "target remote | {} --elf {} --dump {}"
                .format(self.binary, elf, self.coredump)]


def _add_subparser(subparser):
    parser = subparser.add_parser("crashdebug", help="Use CrashDebug as Backend.")
    parser.add_argument(
            "--dump",
            dest="coredump",
            default="coredump.txt",
            help="Path to coredump file.")
    parser.set_defaults(backend=lambda args: CrashProbeBackend(args.coredump))
    return parser

