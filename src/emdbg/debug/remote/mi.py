# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from contextlib import contextmanager
import time
import os
import threading
import signal
import logging
from .gdb import Interface
LOGGER = logging.getLogger(__name__)
from ...logger import VERBOSITY


class Gdb(Interface):
    """
    Provides access to the GDB command prompt using the [GDB/MI protocol][gdbmi].

    .. note:: The Machine Interface protocol is not easily human-readable.
        The GDB output will be formatted using the GDB/MI protocol, which needs
        (simple) post-processing to convert into a normal log again.
        This is especially important when logging GDB output to a file using the
        `set logging enabled on` GDB command.

    [gdbmi]: https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html
    """
    def __init__(self, backend: "emdbg.debug.ProbeBackend", mi: "pygdbmi.gdbcontroller.GdbController"):
        """
        :param backend: a debug backend implementation.
        :param mi: GdbController with the command string.
        """
        super().__init__(backend)
        self.mi = mi
        self.type = "mi"

        self._run_thread = True
        self._command_is_done = False
        self._payloads = []
        self._continue_timeout = -1
        self._response_thread = threading.Thread(target=self._handle_responses)
        self._response_thread.start()

    def _handle_responses(self):
        while self._run_thread:
            responses = self.mi.io_manager.get_gdb_response(timeout_sec=0, raise_error_on_timeout=False)
            for response in responses:
                # print(response)
                if response["type"] == "result" and response["message"] in ["done", "running"]:
                    self._command_is_done = True
                elif response["type"] == "console":
                    if payload := response["payload"].encode("latin-1").decode('unicode_escape'):
                        payload = payload.replace("\\e", "\033")
                        self._payloads.append(payload)
                        if "#" not in payload or VERBOSITY >= 3:
                            LOGGER.debug(payload)
            time.sleep(0.01)

    def read(self, clear=True):
        p = self._payloads
        if clear: self._payloads = []
        return p

    def _write(self, cmd):
        LOGGER.debug(f"(gdb) {cmd}")
        self.mi.write(cmd, timeout_sec=0, raise_error_on_timeout=False, read_response=False)

    def execute(self, cmd, timeout=1, to_string=False) -> str | None:
        self._command_is_done = False
        self._payloads = []
        self._write(cmd)
        while(not self._command_is_done and timeout > 0):
            time.sleep(0.1)
            timeout -= 0.1
        if to_string:
            return "\n".join(self._payloads)

    def quit(self):
        self._run_thread = False
        self._response_thread.join(timeout=1)
        self.mi.exit()
