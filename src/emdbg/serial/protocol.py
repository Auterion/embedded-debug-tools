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
from .utils import find_serial_port, ansi_escape
from ..utils import add_datetime as add_dt

_LOGGER = logging.getLogger("serial:nsh")


class _CmdReader(Protocol):
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

    def clear_input(self):
        self.device.reset_input_buffer()
        self.stream = ""

    def clear_output(self):
        self.device.reset_output_buffer()

    def clear(self):
        self.clear_output()
        self.clear_input()


class CommandPrompt:
    """
    Manages a command prompt, in particular, receiving data in the background
    and logging it out to the INFO logger.
    Several convenience methods allow you to send a command and receive its
    response, or wait for a certain pattern to arrive in the stream.
    """
    _TIMEOUT = 3

    def __init__(self, reader_thread: ReaderThread, protocol: _CmdReader,
                 prompt: str = None, newline: str = None):
        """
        Use the `nsh` context manager to build this class correctly.

        :param reader_thread: The background reader thread.
        :param protocol: The command prompt protocol.
        :param prompt: Optional prefix of the command prompt (default empty string).
        :param newline: The newline characters used in the prompt (default `\\r\\n`).
        """
        self._serial = protocol
        self._reader_thread = reader_thread
        self._serial._data_received = self._print
        self._print_data = ""
        self._prompt = "" if prompt is None else prompt
        self._newline = "\r\n" if newline is None else newline
        self.filter_ansi_escapes = True
        """Filter ANSI escape codes from the output."""
        self._logfile = None
        self.clear()

    def _write_line(self, line):
        self._reader_thread.write((line + "\n").encode("utf-8"))

    def _print(self, data: str):
        self._print_data += data
        if self._newline in self._print_data:
            *lines, self._print_data = self._print_data.split(self._newline)
            for line in self._filter(lines):
                _LOGGER.debug(line)
                if self._logfile is not None:
                    self._logfile.write(line + "\n")

    def _filter(self, lines):
        if self.filter_ansi_escapes:
            lines = list(map(ansi_escape, lines))
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

    def _join(self, lines: list[str]) -> str | None:
        return self._newline.join(lines) if lines else None

    def clear(self):
        """Clear the receive and transmit buffers."""
        self._serial.clear()
        self._print_data = ""

    def log_to_file(self, filename: Path | str, add_datetime: bool = False) -> Path:
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

    def read_lines(self, timeout: float = _TIMEOUT) -> str | None:
        """
        Return any lines received within `timeout`.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param timeout: seconds to wait until new lines arrive.

        :return: received lines or None on timeout
        """
        lines = self._filter(self._read_packets(self._newline, timeout))
        return self._join(lines)

    def wait_for(self, pattern: str, timeout: float = _TIMEOUT) -> str | None:
        """
        Waits for a regex pattern to appear in a line in the stream.
        This function reads any new received lines and searches for `pattern` in
        every line. If the line matches, all lines are returned.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param pattern: regex pattern to search for via `re.search`. To match
                        line beginnings and ends you must use `^pattern$`.
        :param timeout: seconds to wait until new lines arrive.

        :return: received lines until matched pattern or None on timeout
        """
        lines = ""
        start = time.time()
        while True:
            if time.time() - start > timeout:
                break
            if (new_lines := self.read_lines(0)) is not None:
                lines += new_lines
                if re.search(pattern, new_lines):
                    return lines
            time.sleep(0.1)
        _LOGGER.warning(f"Waiting for '{pattern}' timed out after {timeout:.1f}s!")
        return None

    def wait_for_prompt(self, timeout: float = _TIMEOUT) -> list[str]:
        """
        Waits to the prompt to arrive in the stream.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines until the prompt arrives.
        """
        if prompts := self._read_packets(self._newline + self._prompt, timeout):
            prompt = self._prompt + self._prompt.join(prompts)
            return self._join(self._filter(prompt.split(self._newline)))
        _LOGGER.warning(f"Waiting for '{self._prompt}' prompt timed out after {timeout:.1f}s!")
        return None

    def command(self, command: str, timeout: float = _TIMEOUT) -> str | None:
        """
        Send a command and return all lines until the next prompt.
        If the command is asynchronous, you need to poll for new lines separately.
        Note that any ANSI escape codes (for color or cursor position) are
        filtered out.

        :param command: command string to send to the command prompt.
        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines from the command issue until the next prompt arrives.
        """
        self._serial.clear()
        self._write_line(command)
        if timeout is not None:
            return self.wait_for_prompt(timeout)

    def command_nowait(self, command: str):
        """
        Send a command to the command prompt without waiting for a response.

        :param command: command string to send to the command prompt.
        """
        self.command(command, None)

    def reboot(self, timeout: int = 15) -> str | None:
        """
        Send the reboot command and wait for the reboot to be completed.

        :param timeout: seconds to wait until the prompt arrives.

        :return: all lines from reboot until the next prompt.
        """
        return self.command("reboot", timeout)

    def is_alive(self, timeout: float = _TIMEOUT, attempts: int = 4) -> bool:
        """
        Check if the command prompt is responding to newline inputs with a prompt.
        The total timeout is `attempts * timeout`!

        :param timeout: seconds to wait until the prompt arrives.
        :param attempts: number of times to send a newline and wait.
        :return: `True` is command prompt responds, `False` otherwise
        """
        self._serial.clear()
        attempt = 0
        timeout = timeout / attempts
        while attempt < attempts:
            self._write_line("")
            if self.wait_for_prompt(timeout) is not None:
                return True
            attempt += 1
        return False


# -----------------------------------------------------------------------------
@contextmanager
def cmd(serial_or_port: str, baudrate: int = 115200, prompt: str = None, newline: str = None):
    """
    Opens a serial port with the `serial` number or filepath and closes it again.

    :param serial_or_port: the serial number or the filepath of the port to
                           connect to.
    :param baudrate: the baudrate to use.
    :param prompt: Optional prefix of the command prompt.
    :param newline: The newline characters used in the prompt.

    :raises `SerialException`: if serial port is not found.

    :return: yields an initialized `CommandPrompt` object.
    """
    cmd = None
    if "/" in serial_or_port:
        ttyDevice = serial_or_port
    else:
        ttyDevice = find_serial_port(serial_or_port).device
    try:
        _LOGGER.info(f"Starting on port '{serial_or_port}'..."
                     if serial_or_port else "Starting...")
        device = Serial(ttyDevice, baudrate=baudrate)
        reader_thread = ReaderThread(device, lambda: _CmdReader(device))
        with reader_thread as reader:
            cmd = CommandPrompt(reader_thread, reader, prompt, newline)
            yield cmd
    finally:
        if cmd is not None: cmd.log_to_file(None)
        _LOGGER.debug("Stopping.")


@contextmanager
def nsh(serial_or_port: str, baudrate: int = 57600):
    """
    Same as `cmd()` but with a `nsh> ` prompt for use with PX4.
    """
    with cmd(serial_or_port, baudrate, "nsh> ") as nsh:
        yield nsh


# -----------------------------------------------------------------------------
# We need to monkey patch the ReaderThread.run() function to prevent a
# "device not ready" error to abort the reader thread.
def _patched_run(self):
    from serial import SerialException
    self.serial.timeout = 0.1
    self.protocol = self.protocol_factory()
    try:
        self.protocol.connection_made(self)
    except Exception as e:
        self.alive = False
        self.protocol.connection_lost(e)
        self._connection_made.set()
        return
    error = None
    self._connection_made.set()
    while self.alive and self.serial.is_open:
        try:
            data = self.serial.read(self.serial.in_waiting or 1)
        except SerialException as e:
            if self.alive and "readiness" in str(e):
                # _LOGGER.debug(e)
                continue
            error = e
            break
        else:
            if data:
                try:
                    self.protocol.data_received(data)
                except Exception as e:
                    error = e
                    break
    self.alive = False
    self.protocol.connection_lost(error)
    self.protocol = None

ReaderThread.run = _patched_run
