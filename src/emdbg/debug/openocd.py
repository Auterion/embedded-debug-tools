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
import telnetlib
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
                 search: list[Path] = None):
        """
        :param commands: list of commands to execute on launch.
        :param config: list of configuration files to execute on launch.
        :param search: list of directories to search configuration files in.
        """
        super().__init__(":3333")
        self.commands = utils.listify(commands)
        self.config = utils.listify(config)
        self.search = utils.listify(search)
        self.process = None

    def start(self):
        self.process = call(self.commands, self.config, self.search,
                            blocking=False, silent=True)
        LOGGER.info(f"Starting {self.process.pid}...")

    def stop(self):
        if self.process is not None:
            LOGGER.info(f"Stopping {self.process.pid}.")
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
            os.waitpid(os.getpgid(self.process.pid), 0)
            self.process = None


def call(commands: list[str] = None, config: list[Path] = None,
         search: list[Path] = None, blocking: bool = True,
         silent: bool = False)  -> "int | subprocess.Popen":
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
    :param blocking: Run in current process as a blocking call.
                     Set to `False` to run in a new subprocess.
    :param silent: Disable any reporting from `openocd`.

    :return: The process return code if `blocking` or the Popen object.
    """
    commands = ["init"] + utils.listify(commands)
    config = utils.listify(config)
    search = utils.listify(search)
    if silent:
        null_file = "/dev/null"
        commands.append("log_output " + null_file)

    # Provide additional search paths via the OPENOCD_SCRIPTS environment variable
    # See http://openocd.org/doc/html/Running.html
    # os.environ.get("OPENOCD_SCRIPTS", "")

    binary = os.environ.get("PX4_OPENOCD", "openocd")

    command_openocd = "{} {} {} {}".format(
        binary,
        " ".join(map('-s "{}"'.format, search)),
        " ".join(map('-f "{}"'.format, config)),
        " ".join(map('-c "{}"'.format, commands))
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
            search: list[Path] = None) -> int:
    """
    Loads the source file into the microcontroller and resets the device.

    :param commands: list of commands to execute on launch.
    :param config: list of configuration files to execute on launch.
    :param search: list of directories to search configuration files in.
    :param source: path to a `.elf` file to upload.

    :return: the process return code of openocd
    """
    from .gdb import call as gdb_call
    backend = OpenOcdBackend(commands, config, search)
    gdb_cmds = ["monitor reset halt", "load", "monitor reset run", "quit"]
    return gdb_call(backend, source, ui="batch", commands=gdb_cmds)
    # Unfortunately, the OpenOCD program command seems to erase Flash sector 0
    # even if the ELF file has an offset. This overwrites the bootloader and
    # bricks the FMU, so we use GDB instead.
    # commands = utils.listify(commands) + \
    #     [f"program {Path(source).absolute()} preverify verify reset exit"]
    # return call(commands=commands, config=config, search=search)


def reset(commands: list[str] = None, config: list[Path] = None,
          search: list[Path] = None) -> int:
    """
    Resets the device via OpenOCD.

    :param commands: list of commands to execute on launch.
    :param config: list of configuration files to execute on launch.
    :param search: list of directories to search configuration files in.

    :return: the process return code of OpenOCD
    """
    commands = utils.listify(commands) + ["reset", "shutdown"]
    return call(commands=commands, config=config, search=search)


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
    parser.set_defaults(backend=lambda args:
        OpenOcdBackend([f"adapter speed {args.speed}"] +
                       utils.listify(args.ocommands),
                       args.oconfig, args.osearch))
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
        exit(reset(commands, config, args.searchdirs))

    if args.command == "run":
        exit(call(commands, config, args.searchdirs, blocking=True))

    if args.command == "upload":
        exit(program(args.source, commands, config, args.searchdirs))

    LOGGER.error("Unknown command!")
    exit(1)
