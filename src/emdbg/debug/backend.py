# Copyright (c) 2020-2022, Niklas Hauser
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager


class ProbeBackend:
    """
    Base class for starting and stopping debug probes and attaching GDB to them.
    """
    def __init__(self, remote: str = None):
        """
        :param remote: Extended remote location.
        """
        self.remote = remote
        self.name = "remote"

    def init(self, elf: Path) -> list[str]:
        """
        Returns a list of GDB commands that connect GDB to the debug probe.
        The default implementation returns `target extended-remote {self.remote}`.
        """
        return ["target extended-remote {}".format(self.remote)] if self.remote else []

    def start(self):
        """
        Starts the debug probe as a non-blocking subprocess.
        """
        pass

    def stop(self):
        """
        Halts the debug probe process.
        """
        pass

    @contextmanager
    def scope(self):
        """
        Starts and stops the debug probe process within this scope.
        """
        try:
            self.start()
            yield
        finally:
            self.stop()

