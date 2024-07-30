# Copyright (c) 2020-2022, Niklas Hauser
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: gdb.md

## Python API
"""

from __future__ import annotations
import os
import sys
import subprocess
import signal
import tempfile
import shlex
import time
from pathlib import Path
from contextlib import contextmanager

import logging
LOGGER = logging.getLogger("debug:gdb")

from .utils import listify
from .backend import ProbeBackend
from . import remote

# -----------------------------------------------------------------------------
def command_string(backend: ProbeBackend, source: Path = None,
                   config: list[Path] = None, commands: list[str] = None,
                   ui: str = None, svd: Path = None, socket: Path = None,
                   with_python: bool = True, coredump: Path = None) -> str:
    """
    Constructs a command string to launch GDB with the correct options.
    By default, this disables pagination and command confirmation.

    :param backend: a debug backend implementation.
    :param source: Path to a ELF file.
    :param config: List of GDB configuration files.
    :param commands: List of GDB commands to execute during launch.
    :param ui: The frontend configuration for GDB
               - `batch` or None: No UI, launches with `-nx -nh -batch`.
               - `cmd`: Default GDB UI with only a command prompt available.
               - `tui`: Launches in text user interface with layout split.
               - `gdbgui`: Launches in background using GDBGUI as frontend.
    :param svd: Path to the CMSIS-SVD file for the connected device.
    :param socket: Path to socket file, which is used for RPyC communication.
    :param with_python: Uses `arm-none-eabi-gdb-py3` and loads the Python
                        debug modules in `emdbg.debug.px4` as `px4`.
    """
    debug_dir = Path(__file__).parent.resolve()
    cmds = [
        "set pagination off", "set print pretty", "set history save",
        "set mem inaccessible-by-default off", "set confirm off",
        "set filename-display absolute", "set disassemble-next-line on",
        "maintenance set internal-error backtrace on",
        "maintenance set internal-warning backtrace on",
        "set substitute-path /__w/PX4_firmware_private/PX4_firmware_private/ .",
        f"source {debug_dir}/data/orbuculum.gdb",
        f"source {debug_dir}/data/cortex_m.gdb"]
    if (backend_gdb := debug_dir / f"data/{backend.name}.gdb").exists():
        cmds += [f"source {backend_gdb}"]
    cmds += listify(backend.init(source))
    args = [f"-c {coredump}"] if coredump else []
    args += [f'-ex "{a}"' for a in cmds] + ["-q"]
    args += list(map('-x "{}"'.format, listify(config)))

    gdb = "arm-none-eabi-gdb"
    if with_python or socket:
        gdb += "-py3"
        # Import packages from both the host the from emdbg
        args += [f'-ex "python import sys; sys.path.append(\'{debug_dir}\');"']
        args += [f'-ex "python import sys; sys.path.append(\'{path}\');"'
                 for path in sys.path if "-packages" in path]
        # We need to do this terrible hackery since pkg_resources fails on the first import
        args += ['-ex "python exec(\'try: import cmsis_svd;\\\\nexcept: pass\\\\nimport cmsis_svd\')"',
                 '-ex "python exec(\'try: import arm_gdb;\\\\nexcept: pass\\\\nimport arm_gdb\')"']
        # If available, set the default SVD file here
        if svd:
            args += [f'-ex "python import px4; px4._SVD_FILE=\'{svd}\'"']
        # Finally we can import the PX4 GDB user commands
        args += [f'-ex "source {debug_dir}/remote/px4.py"']

    if socket:
        # Import the API bridge that uses rpyc
        args += [f'-ex "python socket_path = \'{socket}\'"',
                 f'-ex "source {debug_dir}/remote/gdb_api_bridge.py"']
        cmd = "{gdb} -nx -nh {args} {source}"

    elif ui is None or "batch" in ui:
        cmd = "{gdb} -nx -nh -batch {args} {source}"

    elif "cmd" in ui:
        cmd = "{gdb} {args} {source}"

    elif "tui" in ui:
        cmd = '{gdb} -tui -ex "layout split" -ex "focus cmd" {args} -ex "refresh" {source}'

    elif "gdbgui" in ui:
        cmd = "gdbgui {source} --gdb-cmd='{gdb} {args} {source}'"

    else:
        raise ValueError("Unknown UI mode! '{}'".format(ui))

    args += list(map('-ex "{}"'.format, listify(commands)))
    return cmd.format(gdb=gdb, args=" ".join(args), source=source or "")


# -----------------------------------------------------------------------------
@contextmanager
def call_rpyc(backend: ProbeBackend, source: Path, config: list[Path] = None,
              commands: list[str] = None, svd: Path = None) -> remote.rpyc.Gdb:
    """
    Launches GDB in the background and connects to it transparently via a RPyC
    bridge. You can therefore use the [GDB Python API][gdbpy] as well as the
    modules in `emdbg.debug.px4` directly from within this process instead of
    using the GDB command line.

    This function returns a `remote.rpyc.Gdb` object, which can be used as a
    substitute for `import gdb`, which is only available *inside* the GDB
    Python environment.
    Note, however, that the access is quite slow, since everything has to be
    communicated through asynchronous IPC.

    [gdbpy]: https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html

    :param backend: a debug backend implementation.
    :param source: Path to a ELF file.
    :param config: List of GDB configuration files.
    :param commands: List of GDB commands to execute during launch.
    :param svd: Path to the CMSIS-SVD file for the connected device.

    :return: `remote.rpyc.Gdb` object which can be used instead of `import gdb`.
    """
    from rpyc import BgServingThread
    from rpyc.utils.factory import unix_connect

    with tempfile.TemporaryDirectory() as socket_dir, backend.scope():
        socket = Path(socket_dir) / "socket"
        gdb_command = command_string(backend, source, config, commands, svd=svd, socket=socket)
        rgdb = None
        try:
            LOGGER.debug(gdb_command)
            rgdb_process = subprocess.Popen(gdb_command, cwd=os.getcwd(),
                                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                            start_new_session=True, shell=True)
            LOGGER.info(f"Starting {rgdb_process.pid}...")
            # TODO: Add a timeout so it doesn't get stuck forever
            while(True):
                try:
                    conn = unix_connect(str(socket))
                    break
                except (ConnectionRefusedError, FileNotFoundError):
                    time.sleep(0.1)

            BgServingThread(conn, callback=lambda: None)
            rgdb = remote.rpyc.Gdb(conn, backend, rgdb_process)
            yield rgdb

        except KeyboardInterrupt:
            pass

        finally:
            LOGGER.info(f"Stopping {rgdb_process.pid}.")
            if rgdb is not None:
                rgdb.quit()
            else:
                os.killpg(os.getpgid(rgdb_process.pid), signal.SIGQUIT)
            os.waitpid(os.getpgid(rgdb_process.pid), 0)

# -----------------------------------------------------------------------------
@contextmanager
def call_mi(backend: ProbeBackend, source: Path = None, config: list[Path] = None,
            commands: list[str] = None, svd: Path = None,
            with_python: bool = True) -> remote.mi.Gdb:
    """
    Launches GDB in the background using [pygdbmi][] and connects to its command
    prompt via the [GDB/MI Protocol][gdbmi].
    This method does not allow accessing the Python API directly, instead you
    must issue command strings inside the GDB command prompt.
    However, this method is significantly faster and most stable than `call_rpyc()`.

    :param backend: a debug backend implementation.
    :param source: Path to a ELF file.
    :param config: List of GDB configuration files.
    :param commands: List of GDB commands to execute during launch.
    :param svd: Path to the CMSIS-SVD file for the connected device.
    :param with_python: Uses `arm-none-eabi-gdb-py3` and loads the Python
                        debug modules in `emdbg.debug.px4` as `px4`.

    :return: `remote.mi.Gdb` object which can be used to issue commands and read
             the responses.

    [gdbmi]: https://sourceware.org/gdb/onlinedocs/gdb/GDB_002fMI.html
    [pygdbmi]: https://cs01.github.io/pygdbmi/
    """
    from pygdbmi.gdbcontroller import GdbController

    gdb_command = command_string(backend, source, config, commands, "cmd", svd, with_python=with_python)
    gdb_command += " --interpreter=mi3"


    with backend.scope():
        rgdb = None
        try:
            LOGGER.info("Starting...")
            LOGGER.debug(gdb_command)
            mi = GdbController(shlex.split(gdb_command))
            rgdb = remote.mi.Gdb(backend, mi)
            yield rgdb

        finally:
            if rgdb is not None:
                rgdb.quit()
            LOGGER.info("Stopping.")


# -----------------------------------------------------------------------------
def _empty_signal_handler(sig, frame):
    pass

def call(backend: ProbeBackend, source: Path = None, config: list[Path] = None,
         commands: list[str] = None, ui: str = None, svd: Path = None,
         with_python: bool = True, coredump: Path = None) -> int:
    """
    Launches the backend in the background and GDB as a blocking process in
    the foreground for user interaction.

    :param backend: a debug backend implementation.
    :param source: Path to a ELF file.
    :param config: List of GDB configuration files.
    :param commands: List of GDB commands to execute during launch.
    :param ui: The frontend configuration for GDB
               - `cmd`: Default GDB UI with only a command prompt available.
               - `tui`: Launches in text user interface with layout split.
               - `gdbgui`: Launches in background using GDBGUI as frontend.
    :param svd: Path to the CMSIS-SVD file for the connected device.
    :param with_python: Uses `arm-none-eabi-gdb-py3` and loads the Python
                        debug modules in `emdbg.debug.px4` as `px4`.
    """
    gdb_command = command_string(backend, source, config, commands, ui, svd,
                                 with_python=with_python, coredump=coredump)

    signal.signal(signal.SIGINT, _empty_signal_handler)
    with backend.scope():
        try:
            LOGGER.info("Starting...")
            LOGGER.debug(gdb_command)
            # This call is now blocking
            return subprocess.call(gdb_command, cwd=os.getcwd(), shell=True)
        except KeyboardInterrupt:
            pass
        finally:
            LOGGER.info("Stopping.")


# -----------------------------------------------------------------------------
def _add_subparser(subparser):
    parser = subparser.add_parser("remote", help="Use a generic extended remote as Backend.")
    parser.add_argument(
        "--port",
        default="localhost:3333",
        help="Connect to this host:port.")
    parser.set_defaults(backend=lambda args: ProbeBackend(args.port))

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse, emdbg
    from . import jlink, crashdebug, openocd

    parser = argparse.ArgumentParser(description="Debug with GDB")
    parser.add_argument(
        "--elf",
        dest="source",
        type=Path,
        help="The ELF files to use for debugging.")
    parser.add_argument(
        "--ui",
        default="cmd",
        choices=["tui", "gdbgui", "cmd", "batch"],
        help="Use GDB via TUI or GDBGUI.")
    parser.add_argument(
        "-py", "--python",
        dest="with_python",
        action="store_true",
        default=False,
        help="Use GDB with Python API and load PX4 tools.")
    parser.add_argument(
        "-c", "--core",
        type=Path,
        default=None,
        help="Use coredump file.")
    parser.add_argument(
        "--svd",
        type=Path,
        help="The CMSIS-SVD file to use for this device, requires `--python` flag.")
    parser.add_argument(
        "-x",
        dest="config",
        action="append",
        type=Path,
        help="Use these GDB init files.")
    parser.add_argument(
        "-ex",
        dest="commands",
        action="append",
        help="Extra GDB commands.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level.")

    subparsers = parser.add_subparsers(title="Backend", dest="backend")

    # Add generic backends
    _add_subparser(subparsers)
    # Add specific backends
    crashdebug._add_subparser(subparsers)
    jlink._add_subparser(subparsers)
    openocd._add_subparser(subparsers)

    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    call(args.backend(args) if args.backend else ProbeBackend(), ui=args.ui,
         source=args.source, config=args.config, commands=args.commands,
         svd=args.svd, with_python=args.with_python, coredump=args.core)

