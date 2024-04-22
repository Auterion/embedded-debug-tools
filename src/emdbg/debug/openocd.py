# Copyright (c) 2020-2022, Niklas Hauser
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: openocd.md
"""

from __future__ import annotations
import os
import time
import signal
import logging
import tempfile
import platform
import subprocess
from pathlib import Path

from . import utils
from .backend import ProbeBackend

LOGGER = logging.getLogger("debug:openocd")

# -----------------------------------------------------------------------------
class OpenOcdBackend(ProbeBackend):
    """
    OpenOCD specific debug backend implementation. Starts `openocd` in
    its own subprocess and connects GDB to port `3333` of the localhost.

    See `call()` for additional information.
    """
    def __init__(self, commands: list[str] = None, config: list[Path] = None,
                 search: list[Path] = None, serial: str = None):
        """
        :param commands: list of commands to execute on launch.
        :param config: list of configuration files to execute on launch.
        :param search: list of directories to search configuration files in.
        :param serial: serial number of debug probe.
        """
        super().__init__(":3333")
        self.commands = utils.listify(commands)
        self.config = utils.listify(config)
        self.search = utils.listify(search)
        self.serial = serial
        self.process = None
        self.name = "openocd"

    def start(self):
        self.process = call(self.commands, self.config, self.search,
                            blocking=False, log_output=False, serial=self.serial)
        LOGGER.info(f"Starting {self.process.pid}...")

    def stop(self):
        if self.process is not None:
            LOGGER.info(f"Stopping {self.process.pid}.")
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            os.waitpid(os.getpgid(self.process.pid), 0)
            self.process = None


def call(commands: list[str] = None, config: list[Path] = None,
         search: list[Path] = None, log_output: Path | bool = None,
         flags: str = None, blocking: bool = True, serial: str = None) -> "int | subprocess.Popen":
    """
    Starts `openocd` and connects to the microcontroller without resetting the
    device. You can overwrite the default binary by exporting an alternative in
    your environment:

    ```sh
    export PX4_OPENOCD=path/to/openocd
    ```

    :param commands: list of commands to execute on launch.
    :param config: list of configuration files to execute on launch.
    :param search: list of directories to search configuration files in.
    :param log_output: Redirect OpenOCD stdout output to a file, or disable
                       entirely via `False`.
    :param flags: Additional flags
    :param blocking: Run in current process as a blocking call.
                     Set to `False` to run in a new subprocess.
    :param serial: serial number of debug probe.

    :return: The process return code if `blocking` or the Popen object.
    """
    if log_output == False: log_output = "/dev/null"
    cmds = [f"log_output {log_output}"] if log_output is not None else []
    cmds += [f"adapter serial {serial}"] if serial is not None else []
    cmds += ["init"] + utils.listify(commands)
    config = utils.listify(config)
    search = utils.listify(search)


    # Provide additional search paths via the OPENOCD_SCRIPTS environment variable
    # See http://openocd.org/doc/html/Running.html
    # os.environ.get("OPENOCD_SCRIPTS", "")

    binary = os.environ.get("PX4_OPENOCD", "openocd")

    command_openocd = "{} {} {} {} {}".format(
        binary, flags or "",
        " ".join(map('-s "{}"'.format, search)),
        " ".join(map('-f "{}"'.format, config)),
        " ".join(map('-c "{}"'.format, cmds))
    )
    LOGGER.debug(command_openocd)

    kwargs = {"cwd": os.getcwd(), "shell": True}
    if blocking:
        return subprocess.call(command_openocd, **kwargs)

    # We have to start openocd in its own session ID, so that Ctrl-C in GDB
    # does not kill OpenOCD.
    kwargs["start_new_session"] = True
    return subprocess.Popen(command_openocd, **kwargs)


# -----------------------------------------------------------------------------
def itm(backend, fcpu: int, baudrate: int = None) -> int:
    """
    Launches `openocd` and configured ITM output on the SWO pin.
    The data is written into a temporary file, which is `tail`'ed for display.

    :param backend: A OpenOCD backend.
    :param fcpu: CPU frequency of the target.
    :param baudrate: optional frequency of the SWO connection.

    :return: the process return code
    """
    if not fcpu:
        raise ValueError("fcpu must be the CPU/HCLK frequency!")

    with tempfile.NamedTemporaryFile() as tmpfile:
        backend.commands += [
            "tpiu create itm.tpiu -dap [dap names] -ap-num 0 -protocol uart",
           f"itm.tpiu configure -traceclk {fcpu} -pin-freq {baudrate or 2000000} -output {tmpfile}",
            "itm.tpiu enable",
            "tpiu init",
            "itm port 0 on",
        ]
        # Start OpenOCD in the background
        with backend.scope():
            # Start a blocking call to monitor the log file
            # TODO: yield out new log lines in the future
            try:
                subprocess.call("tail -f {}".format(tmpfile.name),
                                cwd=os.getcwd(), shell=True)
            except KeyboardInterrupt:
                pass
    return 0

def rtt(backend, channel: int = 0) -> int:
    """
    Launches the backend in the background and connects a telnet client to the
    Real-Time Transfer process. You can disconnect with Ctrl+D.

    :param backend: A OpenOCD backend object.
    :param channel: The RTT channel to connect to.

    :return: the process return code
    """
    backend.commands += [
        "rtt setup 0x20000000 256000",
        "rtt start",
        "rtt polling_interval 1",
       f"rtt server start {9090 + channel} {channel}",
    ]
    import telnetlib
    # Start OpenOCD in the background
    with backend.scope():
        with telnetlib.Telnet("localhost", 9090+channel) as tn:
            try:
                tn.interact()
            except KeyboardInterrupt:
                pass
    return 0


# -----------------------------------------------------------------------------
def program(source: Path, commands: list[str] = None, config: list[Path] = None,
            search: list[Path] = None, serial: str = None) -> int:
    """
    Loads the source file into the microcontroller and resets the device.

    :param commands: list of commands to execute on launch.
    :param config: list of configuration files to execute on launch.
    :param search: list of directories to search configuration files in.
    :param source: path to a `.elf` file to upload.
    :param serial: serial number of debug probe.

    :return: the process return code of openocd
    """
    commands = utils.listify(commands) + \
        [f"program {Path(source).absolute()} verify reset exit"]
    return call(commands=commands, config=config, search=search)

    # Unfortunately, some older OpenOCD versions seems to erase Flash sector 0
    # even if the ELF file has an offset. This overwrites the bootloader and
    # bricks the FMU, so we must use GDB instead.
    # from .gdb import call as gdb_call
    # backend = OpenOcdBackend(commands, config, search, serial)
    # gdb_cmds = ["monitor reset halt", "load", "monitor reset run", "quit"]
    # return gdb_call(backend, source, ui="batch", commands=gdb_cmds, with_python=False)


def reset(commands: list[str] = None, config: list[Path] = None,
          search: list[Path] = None, serial: str = None) -> int:
    """
    Resets the device via OpenOCD.

    :param commands: list of commands to execute on launch.
    :param config: list of configuration files to execute on launch.
    :param search: list of directories to search configuration files in.
    :param serial: serial number of debug probe.

    :return: the process return code of OpenOCD
    """
    commands = utils.listify(commands) + ["reset", "shutdown"]
    return call(commands, config, search, serial=serial)


# -----------------------------------------------------------------------------
def _add_subparser(subparser):
    parser = subparser.add_parser("openocd", help="Use OpenOCD as Backend.")
    parser.add_argument(
        "-f",
        dest="oconfig",
        action="append",
        help="Use these OpenOCD config files.")
    parser.add_argument(
        "-s",
        dest="osearch",
        action="append",
        help="Search in these paths for config files.")
    parser.add_argument(
        "-c",
        dest="ocommands",
        action="append",
        help="Extra OpenOCD commands.")
    parser.add_argument(
        "--speed",
        dest="ospeed",
        type=int,
        default=8000,
        choices=[24000, 8000, 3300, 1000, 200, 50, 5],
        help="SWD baudrate in kHz.")
    parser.add_argument(
        "--serial",
        dest="oserial",
        default=None,
        help="Serial number of debug probe.")
    parser.set_defaults(backend=lambda args:
        OpenOcdBackend([f"adapter speed {args.ospeed}"] +
                       utils.listify(args.ocommands),
                       args.oconfig, args.osearch, args.oserial))
    return parser


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import emdbg

    parser = argparse.ArgumentParser(
        description="OpenOCD debug probe: Upload, reset, and logging")
    parser.add_argument(
        "-f",
        dest="config",
        action="append",
        help="Use these OpenOCD config files.")
    parser.add_argument(
        "-s",
        dest="searchdirs",
        action="append",
        help="Search in these paths for config files.")
    parser.add_argument(
        "-c",
        dest="commands",
        action="append",
        help="Extra OpenOCD commands.")
    parser.add_argument(
        "--speed",
        type=int,
        default=8000,
        choices=[24000, 8000, 3300, 1000, 200, 50, 5],
        help="SWD baudrate in kHz.")
    parser.add_argument(
        "--serial",
        default=None,
        help="Serial number of debug probe.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        help="Verbosity level.")

    subparsers = parser.add_subparsers(title="Command", dest="command")

    subparsers.add_parser("reset", help="Reset the device.")

    subparsers.add_parser("run", help="Run OpenOCD.")

    upload_parser = subparsers.add_parser("upload", help="Upload firmware.")
    upload_parser.add_argument(
        "--source",
        required=True,
        help="The firmware to upload: `.elf` file")

    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    commands = [f"adapter speed {args.speed}"] + utils.listify(args.commands)
    if not (config := args.config):
        config = ["interface/stlink.cfg", "target/stm32f7x.cfg"]

    if args.command == "reset":
        exit(reset(commands, config, args.searchdirs, args.serial))

    if args.command == "run":
        exit(call(commands, config, args.searchdirs, blocking=True, serial=args.serial))

    if args.command == "upload":
        exit(program(args.source, commands, config, args.searchdirs, args.serial))

    LOGGER.error("Unknown command!")
    exit(1)
