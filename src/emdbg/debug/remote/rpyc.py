# Copyright (c) 2015, Gallopsled et al.
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: MIT
# Adapted from https://github.com/Gallopsled/pwntools

from __future__ import annotations
from threading import Event
from contextlib import contextmanager
import time
from .gdb import Interface
import logging
LOGGER = logging.getLogger(__name__)
from ...logger import VERBOSITY

__all__ = ["Gdb"]

class Breakpoint:
    """Mirror of `gdb.Breakpoint` class.

    See https://sourceware.org/gdb/onlinedocs/gdb/Breakpoints-In-Python.html
    for more information.
    """
    def __init__(self, conn, *args, **kwargs):
        """Do not create instances of this class directly.

        Use `Gdb.Breakpoint` instead.
        """
        # Creates a real breakpoint and connects it with this mirror
        self.conn = conn
        self.server_breakpoint = conn.root.set_breakpoint(
            self, hasattr(self, 'stop'), *args, **kwargs)

    def __getattr__(self, item):
        """Return attributes of the real breakpoint."""
        if item in (
                '____id_pack__',
                '__name__',
                '____conn__',
                'stop',
        ):
            # Ignore RPyC netref attributes.
            # Also, if stop() is not defined, hasattr() call in our
            # __init__() will bring us here. Don't contact the
            # server in this case either.
            raise AttributeError()
        return getattr(self.server_breakpoint, item)

    def exposed_stop(self):
        # Handle stop() call from the server.
        return self.stop()


class FinishBreakpoint:
    """Mirror of `gdb.FinishBreakpoint` class.

    See https://sourceware.org/gdb/onlinedocs/gdb/Finish-Breakpoints-in-Python.html
    for more information.
    """

    def __init__(self, conn, *args, **kwargs):
        """Do not create instances of this class directly.

        Use `Gdb.FinishBreakpoint` instead.
        """
        # Creates a real finish breakpoint and connects it with this mirror
        self.conn = conn
        self.server_breakpoint = conn.root.set_finish_breakpoint(
            self, hasattr(self, 'stop'), hasattr(self, 'out_of_scope'),
            *args, **kwargs)

    def __getattr__(self, item):
        """Return attributes of the real breakpoint."""
        if item in (
                '____id_pack__',
                '__name__',
                '____conn__',
                'stop',
                'out_of_scope',
        ):
            # Ignore RPyC netref attributes.
            # Also, if stop() or out_of_scope() are not defined, hasattr() call
            # in our __init__() will bring us here. Don't contact the
            # server in this case either.
            raise AttributeError()
        return getattr(self.server_breakpoint, item)

    def exposed_stop(self):
        # Handle stop() call from the server.
        return self.stop()

    def exposed_out_of_scope(self):
        # Handle out_of_scope() call from the server.
        return self.out_of_scope()


class Gdb(Interface):
    """Mirror of `gdb` module.
    This class uses a RPyC to communicate with the GDB subprocess and exchange
    IPC messages about the state of the system. You can therefore access
    everything that the GDB Python API can in this process and it gets
    synchronized automatically. However, keep in mind that access may be
    significantly slower than when using the Python API in GDB directly.

    See the [GDB Python API documentation](https://sourceware.org/gdb/onlinedocs/gdb/Basic-Python.html).
    """

    def __init__(self, conn, backend, process):
        """Do not create instances of this class directly.

        Use `emdbg.debug.gdb.call_rpyc()` instead.
        """
        super().__init__(backend)
        self.conn = conn
        self.process = process
        self.type = "rpyc"

        class _Breakpoint(Breakpoint):
            def __init__(self, *args, **kwargs):
                super().__init__(conn, *args, **kwargs)
        class _FinishBreakpoint(FinishBreakpoint):
            def __init__(self, *args, **kwargs):
                super().__init__(conn, *args, **kwargs)

        self.Breakpoint = _Breakpoint
        """
        Mirror of [`gdb.Breakpoint` class](https://sourceware.org/gdb/onlinedocs/gdb/Breakpoints-In-Python.html).
        """
        self.FinishBreakpoint = _FinishBreakpoint
        """
        Mirror of [`gdb.FinishBreakpoint` class](https://sourceware.org/gdb/onlinedocs/gdb/Finish-Breakpoints-in-Python.html).
        """
        self.stopped = Event()

        def stop_handler(event):
            self.stopped.set()

        self.events.stop.connect(stop_handler)

    def __getattr__(self, item):
        return getattr(self.conn.root.gdb, item)

    def wait(self):
        """Wait until the program stops."""
        self.stopped.wait()
        self.stopped.clear()

    def interrupt_and_wait(self) -> bool:
        if not self.interrupted:
            self.execute("interrupt")
            self.wait()
            self.interrupted = True
            return True
        return False

    def continue_nowait(self):
        """Continue the program. Do not wait until it stops again."""
        if self.interrupted:
            self.execute("continue&")
            self.interrupted = False
        time.sleep(0.2)

    def continue_and_wait(self):
        """Continue the program and wait until it stops again."""
        if self.interrupted:
            self.execute("continue&")
            self.interrupted = False
        self.wait()

    def quit(self):
        self.interrupted = False
        self.conn.root.quit()

    def execute(self, cmd, timeout=1, to_string=False) -> str | None:
        if VERBOSITY >= 3: LOGGER.debug(f"(gdb) {cmd}")
        return self.conn.root.gdb.execute(cmd, to_string=to_string)
