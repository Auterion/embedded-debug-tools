# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from serial.tools import list_ports
import re
import logging
_LOGGER = logging.getLogger("serial")


class SerialException(Exception):
    """Exception for all serial port related errors."""
    pass


def find_serial_port(identifier=None):
    """
    Finds the serial port with the `identifier` serial number.
    If not found, an exception is raised with all discovered serial ports in
    the message, or a list of serial ports, if `identifier` is None.

    :raises `SerialException`: if no serial port matches `identifier`.
    :return:
    - The serial port whose serial number matches the `identifier`, or
    - A list of all serial ports if `identifier` is not `None`.
    """
    serials = []
    for port in list_ports.comports():
        if not identifier:
            _LOGGER.debug(f"Using first found serial port '{port.serial_number}'.")
            return port
        if port.serial_number == identifier:
            return port
        serials.append(port)

    if not serials:
        raise SerialException("Unable to find any serial ports!")

    if identifier is not None:
        msg = f"Unable to find '{identifier}' serial port!\n"
        serials = "\n\t- ".join(f"{s}: serial={s.serial_number}" for s in serials)
        msg += f"Available serial ports are:\n\t- {serials}\n"
        raise SerialException(msg)

    return serials


_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

def ansi_escape(line: str) -> str:
    """Removes ANSI escape sequences from a string"""
    return _ANSI_ESCAPE.sub("", line)
