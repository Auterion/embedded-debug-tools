# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from contextlib import contextmanager
import time


class Interface:
    """
    The interface of all GDB remote access implementations.
    """

    def __init__(self, backend: "emdbg.debug.ProbeBackend"):
        self.backend = backend
        self.interrupt_nesting = 0
        self.interrupted = True
        self.type = "base"

    def execute(self, command: str, timeout: float = 1, to_string: bool = False) -> str | None:
        """
        Executes a command on the GDB command prompt and waits for a response.
        If `to_string` is set, it will return the response as a string.

        :param command: The command string to send to the GDB prompt.
        :param timeout: How long to wait for a response in seconds.
        :param to_string: Capture the response as a string and return it.
        """
        raise NotImplementedError

    @contextmanager
    def interrupt_continue(self):
        """
        Interrupts and yields, then continues.
        If the target was already interrupted before entering this scope, it
        will not continue automatically, so that this context can be used in
        nested calls.
        """
        try:
            interrupted = self.interrupt_and_wait()
            self.interrupt_nesting += 1
            yield
        finally:
            self.interrupt_nesting -= 1
            if self.interrupt_nesting == 0 and interrupted:
                self.continue_nowait()

    def interrupt_and_wait(self) -> bool:
        """
        Interrupt the program and wait until it stops.

        :return: `True` if GDB has been interrupted, `False` if it was already interrupted.
        """
        if not self.interrupted:
            self.execute("interrupt")
            self.interrupted = True
            time.sleep(0.2)
            return True
        return False

    def continue_nowait(self) -> bool:
        """
        Continue the program. Do not wait until it stops again.

        :return: `True` if GDB continues running, `False` if it was already running.
        """
        if self.interrupted:
            self.execute("continue&")
            self.interrupted = False
            time.sleep(0.2)
            return True
        return False

    def quit(self):
        """Terminate GDB."""
        raise NotImplementedError
