# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import re
import time
import logging
from contextlib import contextmanager
from pathlib import Path
from serial import Serial
from serial.threaded import ReaderThread, Protocol
from .utils import find_serial_port
from ..utils import add_datetime as add_dt

LOGGER = logging.getLogger("serial:nsh")


class _NshReader(Protocol):
    def __init__(self, device: Serial):
        super().__init__()
        self.stream = ""
        self.device = device
        self._data_received = lambda _: None

    def data_received(self, data: bytes):
        new_stream = data.decode("utf-8", errors="replace")
        self._data_received(new_stream)
        self.stream += new_stream

    def read_packets(self, separator: str) -> list[str]:
        if separator not in self.stream:
            return []
        *packets, self.stream = self.stream.split(separator)
        return packets

    def write_line(self, line: str):
        # Pace the transmission to 1 char / 10ms to not loose character
        for char in (line + "\n"):
            self.device.write(char.encode("utf-8"))
            # self.device.flushOutput()
            time.sleep(0.01)

    def clear_input(self):
        self.device.reset_input_buffer()
        self.stream = ""

    def clear_output(self):
        self.device.reset_output_buffer()

    def clear(self):
        self.clear_output()
        self.clear_input()


# -----------------------------------------------------------------------------
class Nsh:
    """
    Manages the NSH protocol, in particular, receiving data in the background
    and logging it out to the INFO logger.
    Several convenience methods allow you to send a command and receive its
    response, or wait for a certain pattern to arrive in the stream.

    Transmitting a command is intentionally slow to not overflow the NSH receive
    buffers while it is being debugged. Note that the PX4 target needs to be
    running for the NSH to be functional.
    """
    _ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    _NEWLINE = "\r\n"
    _PROMPT = "nsh> "
    _TIMEOUT = 3

    def __init__(self, reader: Protocol):
        """
        Use the `nsh` context manager to build this class correctly.

        :param reader: The background thread reader protocol.
        """
        self._serial = reader
        self._serial._data_received = self._print
        self._print_data = ""
        self.filter_ansi_escapes = True
        self._logfile = None

    def _write_line(self, line):
        self._serial.write_line(line)

    def _print(self, data: str):
        self._print_data += data
        if Nsh._NEWLINE in self._print_data:
            *lines, self._print_data = self._print_data.split(Nsh._NEWLINE)
            for line in self._filter(lines):
                LOGGER.info(line)
                if self._logfile is not None:
                    self._logfile.write(line + "\n")

    def _filter(self, lines):
        if self.filter_ansi_escapes:
            lines = [self._ANSI_ESCAPE.sub('', line) for line in lines]
        return lines

    def _read_packets(self, separator: str, timeout: float = _TIMEOUT) -> list[str]:
        start = time.time()
        while True:
            if packets := self._serial.read_packets(separator):
                return packets
            if time.time() - start > timeout:
                break
            time.sleep(0.1)
        return []

    def clear(self):
        """Clear the receive and transmit buffers."""
        self._serial.clear()
        self._print_data = ""

    def log_to_file(self, filename: Path | str, add_datetime: bool = False):
        """
        Log the received data to `filename` or close the log file.

        :param filename: file to log into. If `None`, the file is closed and
                         logging is disabled.
        :param add_datetime: appends the date and time to the filename.
                             See `emdbg.utils.add_datetime`

        :return: the actual filename with date and time (if selected).
        """
        if self._logfile is not None:
            self._logfile.close()

        if filename is None:
            self._logfile = None
            return None

        filename = add_dt(filename) if add_datetime else Path(filename)
        self._logfile = filename.open("wt")
        return filename


    def read_lines(self, timeout: float = _TIMEOUT) -> list[str]:
        """
        Return any lines received within `timeout`.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param timeout: seconds to wait until new lines arrive.

        :return: list of received lines or an empty list
        """
        return self._filter(self._read_packets(Nsh._NEWLINE, timeout))


    def wait_for(self, pattern: str, timeout: float = _TIMEOUT) -> list[str]:
        """
        Waits for a regex pattern to appear in a line in the stream.
        This function reads any new received lines and searches for `pattern` in
        every line. If the line matches, all lines are returned.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param pattern: regex pattern to search for via `re.search`. To match
                        line beginnings and ends you must use `^pattern$`.
        :param timeout: seconds to wait until new lines arrive.

        :return: list of received lines until matched pattern or an empty list
        """
        lines = []
        start = time.time()
        while True:
            if time.time() - start > timeout:
                break
            new_lines = self.read_lines(0)
            lines.append(new_lines)
            for line in new_lines:
                if re.search(pattern, line):
                    return lines
            time.sleep(0.1)
        LOGGER.warning(f"Waiting for '{pattern}' timed out after {timeout:.1f}s!")
        return []

    def wait_for_prompt(self, timeout: float = _TIMEOUT) -> list[str]:
        """
        Waits to the `nsh> ` prompt to arrive in the stream.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines until the prompt arrives.
        """
        if prompts := self._read_packets(Nsh._NEWLINE + Nsh._PROMPT, timeout):
            prompt = Nsh._PROMPT + Nsh._PROMPT.join(prompts)
            return self._filter(prompt.split(Nsh._NEWLINE))
        LOGGER.warning(f"Waiting for 'nsh> ' prompt timed out after {timeout:.1f}s!")
        return []


    def command(self, command: str, timeout: float = _TIMEOUT) -> list[str]:
        """
        Send a command and return all lines until the next prompt.
        If the command is asynchronous, you need to poll for new lines separately.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param command: command string to send to the NSH.
        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines from the command issue until the next prompt arrives.
        """
        self._serial.clear()
        self._write_line(command)
        if timeout is not None:
            return self.wait_for_prompt(timeout)

    def command_nowait(self, command: str):
        """
        Send a command to the NSH without waiting for a response.

        :param command: command string to send to the NSH.
        """
        self.command(command, None)


    def reboot(self, timeout: int = 15) -> list[str]:
        """
        Send the reboot command and wait for the reboot to be completed.

        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines from reboot until the next prompt.
        """
        return self.command("reboot", timeout)

    def is_alive(self, timeout: float = _TIMEOUT, attempts: int = 4) -> bool:
        """
        Check if the NSH is responding to newline inputs with a `nsh> ` prompt.
        The total timeout is `attempts * timeout`!

        :param timeout: seconds to wait until the prompt arrives.
        :param attempts: number of times to send a newline and wait.
        :return: `True` is NSH responds, `False` otherwise
        """
        self._serial.clear()
        attempt = 0
        timeout = timeout / attempts
        while attempt < attempts:
            self._write_line("")
            if self.wait_for_prompt(timeout):
                return True
            attempt += 1
        return False


# -----------------------------------------------------------------------------
@contextmanager
def nsh(serial: str, baudrate: int = 57600):
    """
    Opens a serial port with the `serial` number and closes it again.

    :param serial: the serial number of the port to connect to.
    :param baudrate: the baudrate to use.

    :raises `SerialException`: if serial port is not found.

    :return: yields an initialized `Nsh` object.
    """
    nsh = None
    port = find_serial_port(serial)
    try:
        LOGGER.info(f"Starting on port '{serial}'..." if serial else "Starting...")
        device = Serial(port.device, baudrate=baudrate, timeout=0.01)
        with ReaderThread(device, lambda: _NshReader(device)) as reader:
            nsh = Nsh(reader)
            yield nsh
    finally:
        if nsh is not None: nsh.log_to_file(None)
        LOGGER.debug("Stopping.")
