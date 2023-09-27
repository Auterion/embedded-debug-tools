# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: jlink.md
"""

from __future__ import annotations
import os
import time
import signal
import platform
import subprocess
import logging
import tempfile
from pathlib import Path

from .backend import ProbeBackend
from . import gdb

LOGGER = logging.getLogger("debug:jlink")


# -----------------------------------------------------------------------------
class JLinkBackend(ProbeBackend):
    """
    J-Link specific debug backend implementation. Starts the `JLinkGDBServer` in
    its own subprocess and connects GDB to port `2331` of the localhost.

    See `call()` for additional information.
    """
    def __init__(self, device: str, speed: int, rtos: Path = None):
        """
        :param device: part name of the microcontroller to debug.
        :param speed: SWD connection baudrate in kHz.
        :param rtos: Path to RTOS plugin for thread-aware debugging.
        """
        super().__init__(":2331")
        self.device = device
        self.speed = speed
        self.rtos = rtos
        self.process = None
        self.name = "jlink"

    def start(self):
        self.process = call(self.device, self.speed, self.rtos,
                            blocking=False, silent=True)
        LOGGER.info(f"Starting {self.process.pid}...")

    def stop(self):
        if self.process is not None:
            LOGGER.info(f"Stopping {self.process.pid}.")
            os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
            os.waitpid(os.getpgid(self.process.pid), 0)
            self.process = None


# -----------------------------------------------------------------------------
def call(device: str, speed: int, rtos: Path = None, blocking: bool = True,
         silent: bool = False) -> "int | subprocess.Popen":
    """
    Starts the `JLinkGDBServer` and connects to the microcontroller without
    resetting the device and without GUI. You can overwrite the default binary
    by exporting an alternative in your environment:

    ```sh
    export PX4_JLINK_GDB_SERVER=path/to/JLinkGDBServer
    ```

    :param device: part name of the microcontroller to debug.
    :param speed: SWD connection baudrate in kHz.
    :param rtos: Path to RTOS plugin for thread-aware debugging.
    :param blocking: Run in current process as a blocking call.
                     Set to `False` to run in a new subprocess.
    :param silent: Disable any reporting from `JLinkGDBServer`.

    :return: The process return code if `blocking` or the Popen object.
    """
    binary = os.environ.get("PX4_JLINK_GDB_SERVER", "JLinkGDBServer")

    command_jlink = f"{binary} -device {device} -speed {speed} -if swd -noreset -nogui"
    if rtos: command_jlink += f" -rtos {Path(rtos).absolute()}"
    if silent: command_jlink += " -silent"

    LOGGER.debug(command_jlink)

    kwargs = {"cwd": os.getcwd(), "shell": True}
    if blocking:
        return subprocess.call(command_jlink, **kwargs)

    # Disconnect the JLink process from this process, so that any Ctrl-C usage
    # in GDB does not get passed on to the JLink process.
    kwargs["start_new_session"] = True
    return subprocess.Popen(command_jlink, **kwargs)


# -----------------------------------------------------------------------------
def itm(device: str, baudrate: int = None, port: int = None) -> int:
    """
    Launches `JLinkSWOViewer`, connects to the microcontroller. You can
    overwrite the default binary by exporting an alternative in your environment:

    ```sh
    export PX4_JLINK_SWO_VIEWER=path/to/JLinkSWOViewer
    ```

    :param device: part name of the microcontroller to debug.
    :param baudrate: optional frequency of the SWO connection.
    :param port: ITM port to display at startup. You can modify this at runtime.

    :return: the process return code
    """
    binary = os.environ.get("PX4_JLINK_SWO_VIEWER", "JLinkSWOViewer")
    command_jlink = f"{binary} -device {device} -itmport {port or 0}"
    if baudrate: command_jlink += f" -swofreq {baudrate}"
    try:
        return subprocess.call(command_jlink, shell=True)
    except KeyboardInterrupt:
        pass


def rtt(backend: JLinkBackend, channel: int = 0) -> int:
    """
    Launches the backend in the background and connects a telnet client to the
    Real-Time Transfer process. You can disconnect with Ctrl+D.

    :param backend: A J-Link backend object.
    :param channel: The RTT channel to connect to.

    :return: the process return code
    """
    import telnetlib
    # Start JLinkGDBServer in the background
    with backend.scope():
        with telnetlib.Telnet("localhost", 19021) as tn:
            try:
                tn.interact()
            except KeyboardInterrupt:
                pass
    return 0

# -----------------------------------------------------------------------------
def program(device: str, speed: int, source: Path, load_addr: int = None) -> int:
    """
    Loads the source file into the microcontroller and resets the device. You can
    overwrite the default binary by exporting an alternative in your environment:

    ```sh
    export PX4_JLINK=path/to/JLinkExe
    ```

    :param device: part name of the microcontroller to program.
    :param speed: SWD connection baudrate in kHz.
    :param source: path to a `.bin`, `.hex`, or `.elf` file to upload.
    :param load_addr: Specifies the start address to load a `.bin` file.

    :return: the process return code of JLink
    """
    binary = os.environ.get("PX4_JLINK", "JLinkExe")
    if load_addr is None and Path(source).suffix == ".bin":
        load_addr = 0x0800_0000
    with tempfile.NamedTemporaryFile() as fcmd:
        # LoadFile erases the correct amount of sectors, then writes the new
        # binary or hex file. We still need to reset afterwards.
        Path(fcmd.name).write_text(f"LoadFile {source} {load_addr or ''}\nReset\nExit")
        jcmd = f"{binary} -device {device} -if swd -speed {speed} " \
               f"-autoconnect 1 -nogui 1 -commandfile {fcmd.name}"
        LOGGER.debug(jcmd)
        return subprocess.call(jcmd, shell=True)

def reset(device: str, speed: int) -> int:
    """
    Resets the device via JLink.

    :param device: part name of the microcontroller to program. You can
                   overwrite the default binary by exporting an alternative in
                   your environment:
                   ```sh
                   export PX4_JLINK=path/to/JLinkExe
                   ```
    :param speed: SWD connection baudrate in kHz.

    :return: the process return code of JLink
    """
    binary = os.environ.get("PX4_JLINK", "JLinkExe")
    with tempfile.NamedTemporaryFile() as fcmd:
        Path(fcmd.name).write_text(f"Reset\nExit")
        jcmd = f"{binary} -device {device} -if swd -speed {speed} " \
               f"-autoconnect 1 -nogui 1 -commandfile {fcmd.name}"
        LOGGER.debug(jcmd)
        return subprocess.call(jcmd, shell=True)


# -----------------------------------------------------------------------------
def _add_subparser(subparser):
    parser = subparser.add_parser("jlink", help="Use JLink as Backend.")
    parser.add_argument(
            "-device",
            required=True,
            help="Connect to this device.")
    parser.add_argument(
            "-speed",
            type=int,
            default=12000,
            help="SWO baudrate in kHz.")
    parser.set_defaults(backend=lambda args: JLinkBackend(args.device))
    return parser


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import emdbg

    parser = argparse.ArgumentParser(
        description="JLink debug probe: Upload, reset, and logging")
    parser.add_argument(
        "-device",
        required=True,
        help="Connect to this device.")
    parser.add_argument(
        "-speed",
        type=int,
        default=12000,
        help="SWD baudrate in kHz.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        help="Verbosity level.")

    subparsers = parser.add_subparsers(title="Command", dest="command")

    subparsers.add_parser("reset", help="Reset the device.")

    subparsers.add_parser("run", help="Run JLinkGDBServer.")

    upload_parser = subparsers.add_parser("upload", help="Upload firmware.")
    upload_parser.add_argument(
        "--source",
        required=True,
        help="The firmware to upload: `.bin`, `.hex`, or `.elf` file")
    upload_parser.add_argument(
        "--load-addr",
        help="The load address of the binary file")

    rtt_parser = subparsers.add_parser("rtt", help="Connect to an RTT channel.")
    rtt_parser.add_argument(
        "--channel",
        type=int,
        default=0,
        help="The RTT channel to connect to.")

    itm_parser = subparsers.add_parser("itm", help="Show ITM log output.")
    itm_parser.add_argument(
        "--baudrate",
        type=int,
        help="Force a baudrate instead of auto-selecting it.")
    itm_parser.add_argument(
        "--channel",
        type=int,
        help="The channel to output.")

    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    if args.command == "reset":
        exit(reset(args.device, args.speed))

    if args.command == "run":
        exit(call(args.device, args.speed, blocking=True))

    if args.command == "upload":
        exit(program(args.device, args.speed, os.path.abspath(args.source)))

    if args.command == "rtt":
        backend = JLinkBackend(args.device, args.speed)
        exit(rtt(backend, args.channel))

    if args.command == "itm":
        exit(itm(args.device, args.baudrate, args.channel))

    LOGGER.error("Unknown command!")
    exit(1)
