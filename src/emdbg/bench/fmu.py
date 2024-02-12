# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: fmu.md
"""

from __future__ import annotations
import time
from functools import cached_property
from pathlib import Path
from contextlib import contextmanager, nullcontext
import emdbg


class Fmu:
    """
    FMU test bench with optional nsh, power, and logic analyzer attachments.
    """
    def _DBGMCU_CONFIG(target):
        # Vector catch all exceptions, but not reset
        common = ["set *0xE000EDFC |= 0x07f0"]
        # Halt all timers and peripherals while debugging
        if "fmu-v5x" in target:
            return ["set *0xE0042008 = 0xffffffff",
                    "set *0xE004200C = 0xffffffff"] + common
        if "fmu-v6x" in target:
            return ["set *0xE00E1034 = 0xffffffff",
                    "set *0xE00E103C = 0xffffffff",
                    "set *0xE00E104C = 0xffffffff",
                    "set *0xE00E1054 = 0xffffffff"] + common
        return []

    def __init__(self, target: str, elf: Path,
                 gdb: "emdbg.debug.remote.gdb.Interface",
                 nsh: "emdbg.serial.protocol.Nsh" = None,
                 power: "emdbg.power.base.Base" = None,
                 io: "emdbg.io.digilent.Digilent" = None):
        self.elf: Path = elf
        """The ELF file under debug"""
        self.gdb: "emdbg.debug.remote.gdb.Interface" = gdb
        """The remote GDB access interface object"""
        self.nsh: "emdbg.serial.protocol.Nsh" = nsh
        """The NSH protocol controller"""
        self.power: "emdbg.power.base.Base" = power
        """The power relay controlling the FMU"""
        self.io: "emdbg.io.digilent.Digilent" = io
        """The Digilent Scope"""
        self._target = target

    def _init(self):
        self.gdb.interrupt_and_wait()
        for cmd in self._DBGMCU_CONFIG(self._target):
            self.gdb.execute(cmd)
        self.restart_system_load_monitor()

    def _deinit(self):
        self.gdb.interrupt_and_wait()
        self.gdb.execute("disconnect")
        self.gdb.interrupted = False
        # Give JLink some time to react to the disconnect before shut down
        time.sleep(1)

    def restart_system_load_monitor(self):
        """See `emdbg.debug.px4.system_load.restart_system_load_monitor`"""
        with self.gdb.interrupt_continue():
            if self.gdb.type == "mi":
                self.gdb.execute("python px4.restart_system_load_monitor(gdb)")
            else:
                emdbg.debug.px4.restart_system_load_monitor(self.gdb)

    def coredump(self, filename: Path = None):
        """
        Dumps the FMU core for later analysis with CrashDebug (see
        `emdbg.debug.crashdebug`).

        :param filename: Default `coredump_{datetime}.txt`.
        """
        with self.gdb.interrupt_continue():
            if False:
                # Connection is remote, therefore we must use slower RPyC interface
                emdbg.debug.px4.coredump(self.gdb, filename=filename)
            else:
                # Executing directly on the GDB process is *significantly* faster!
                if filename: filename = f"--file '{filename}'"
                self.gdb.execute(f"px4_coredump {filename or ''}")

    def upload(self, source: Path = None):
        """
        Uploads the ELF file to the FMU, resets the device, clears the NSH
        :param source: optional path to ELF file, default is the ELF file passed
                       to the constructor.
        """
        with self.gdb.interrupt_continue():
            self.gdb.execute("monitor reset")
            self.gdb.execute(f"load {source or self.elf}", timeout=60)
            self.reset()
            if self.nsh is not None:
                self.nsh.clear()

    def power_on_reset(self, delay_off: float = 1, delay_on: float = 2):
        """
        Disconnects GDB, stops the backend, power cycles the entire bench,
        restarts the backend, reconnects and reinitializes GDB.
        **Only works if initialized with a power relay!**
        """
        if self.power is None:
            LOGGER.warning("Power Relay not configured!")
            return
        # Disconnect and stop the backend
        self._deinit()
        self.gdb.backend.stop()
        # Wait for JLink to shut down, os.waitpid is not enough
        time.sleep(1)

        # Have you tried turning it off and on again?
        self.power.cycle(delay_off, delay_on)

        # Restart and reattach the backend
        self.gdb.backend.start()
        # Wait for JLink to start up again, since it starts non-blocking
        time.sleep(2)
        # Reinitialize GDB to attach back to JLink
        for cmd in self.gdb.backend.init(self.elf):
            self.gdb.execute(cmd)
        self._init()

    def reset(self):
        """Resets the FMU"""
        with self.gdb.interrupt_continue():
            self.gdb.execute("monitor reset")
            self._init()

    def sleep(self, seconds: float, func=None):
        """
        Sleeps and calls `func` every second. This can be useful for polling if
        a condition has happened.
        """
        while(seconds > 0):
            seconds -= 1
            time.sleep(1)
            if func is not None:
                func(seconds)


def _px4_config(px4_directory: Path, target: Path, commands: list[str] = None,
                ui: str = None, speed: int = 16000, backend: str = None) -> tuple:
    if "fmu-v5x" in target:
        device = "STM32F765II"
        config = "fmu_v5x"
    elif "fmu-v6x" in target:
        device = "STM32H753II"
        config = "fmu_v6x"
    else:
        raise ValueError(f"Unknown device for '{target}'!")

    px4_dir = Path(px4_directory).absolute().resolve()
    data_dir = Path(__file__).parent.resolve() / "data"

    if backend in ["stlink", "orbtrace"]:
        config += f"_{backend}.cfg"
        backend_obj = emdbg.debug.OpenOcdBackend(config=[data_dir / config])
    elif backend == "jlink":
        rtos_so = px4_dir / f"platforms/nuttx/NuttX/nuttx/tools/jlink-nuttx.so"
        if not rtos_so.exists(): rtos_so = None
        backend_obj = emdbg.debug.JLinkBackend(device, speed, rtos_so)
    elif isinstance(backend, Path):
        backend_obj = emdbg.debug.CrashProbeBackend(backend)
    elif ":" in backend:
        backend_obj = emdbg.debug.ProbeBackend(backend)
    else:
        raise ValueError(f"Unknown backend '{backend}'!")

    boot_elf = None
    if Path(target).suffix == ".elf":
        elf = Path(target)
    else:
        if (elf := next((px4_dir / "build" / target).glob("*.elf"), None)) is None:
            raise ValueError(f"Cannot find ELF file in build folder '{px4_dir}/build/{target}'!")
        if "_default" in target: # try to find the bootloader elf too
            boot_elf = next((px4_dir / "build" / target.replace("_default", "_bootloader")).glob("*.elf"), None)

    cmds = [f"dir {px4_dir}",
            f"source {data_dir}/fmu.gdb",
            f"python px4._TARGET='{target.lower()}'"]
    if boot_elf is not None:
        cmds += [f"add-symbol-file {boot_elf}"]
    if ui is not None and backend_obj.name != "crashdebug":
        cmds += Fmu._DBGMCU_CONFIG(target)
    cmds += (commands or [])

    return backend_obj, elf, cmds


# -----------------------------------------------------------------------------
@contextmanager
def debug(px4_directory: Path, target: str, serial: str = None,
          digilent: str = None, power: "emdbg.power.base.Base" = None,
          ui: str = None, commands: list[str] = None, with_rpyc: bool = False,
          keep_power_on: bool = True, upload: bool = True, backend: str = None,
          _FmuClass = Fmu) -> Fmu:
    """
    Launches and configures the Fmu test bench.
    1. Switches on the power relay if specified.
    2. Starts the J-Link GDB server in the background.
    3. Launches GDB and connects it to the debug probe backend.
    4. Connects and initializes the NSH if specified.
    5. Connects and initializes the Digilent Scope if specified.
    6. Loads the PX4 specific GDB scripts, the `emdbg.debug.px4`
       modules Python modules, and the `fmu.gdb` script.
    7. Uploads the latest firmware to the FMU.
    8. Yields the test bench in halted reset state.

    :param px4_directory: path to the PX4-Autopilot repository you want to debug.
    :param target: target name as a string, for example, `px4_fmu-v5x`.
                   Can also be a path to an ELF file.
    :param serial: optional serial number of the USB-Serial bridge for the NSH.
                   If `None`, then `Fmu.nsh` is empty and cannot be used.
    :param digilent: optional serial number of the Digilent. If `None`, then
                     `Fmu.io` is empty and cannot be used.
    :param ui: If not `None`, then this launches the interactive debugger via
               `emdbg.debug.gdb.call` instead of the scripting API.
    :param commands: list of additional GDB commands to execute during launch.
    :param with_rpyc: Use the RPyC GDB interface implementation, rather than the
                      GDB/MI interface. See `emdbg.debug.remote`.
    :param keep_power_on: Do not shut off the Fmu after the context has closed.
    :param upload: Automatically upload the firmware after powering on the FMU.
    :param backend: `openocd`, `jlink`, or `IP:PORT` for a GDB server on another machine.

    :return: A configured test bench with the latest firmware.
    """
    backend, elf, cmds = _px4_config(px4_directory, target, commands, ui,
                                     backend=backend or "openocd")

    with (nullcontext() if power is None else power) as pwr:
        try:
            if ui is not None:
                # Manual mode that only connects the debugger (blocking)
                if power: pwr.on()
                yield emdbg.debug.gdb.call(backend, elf, commands=cmds, ui=ui)
            else:
                # Turn off, then connect the serial
                if power: pwr.off()
                serial = emdbg.serial.nsh(serial) if serial is not None else nullcontext()
                scope = emdbg.io.analog_discovery(digilent) if digilent is not None else nullcontext()
                with serial as nsh, scope as io:
                    # Then power on and connect GDB to get the full boot log
                    if power: pwr.on()
                    gdb_call = emdbg.debug.gdb.call_rpyc if with_rpyc else emdbg.debug.gdb.call_mi
                    debugger = gdb_call(backend, elf, commands=cmds)
                    with debugger as gdb:
                        bench = _FmuClass(target, elf, gdb, nsh, pwr, io)
                        if upload: bench.upload()
                        yield bench
                        bench._deinit()
        finally:
            if not keep_power_on:
                pwr.off(delay=0)


# -----------------------------------------------------------------------------
@contextmanager
def shell(serial: str = None, power = None, keep_power_on: bool = True) -> Fmu:
    """
    Launches and configures the Fmu test bench.
    1. Switches on the power relay if specified.
    4. Connects and initializes the NSH if specified.
    8. Yields the NSH after reset state.

    :param serial: optional serial number of the USB-Serial bridge for the NSH.
                   If `None`, then `Fmu.nsh` is empty and cannot be used.
    :param keep_power_on: Do not shut off the Fmu after the context has closed.

    :return: A configured test bench with the latest firmware.
    """

    if power is None: power = nullcontext()
    with power as pwr:
        try:
            # Turn off, then connect the serial
            pwr.off()
            serial = emdbg.serial.nsh(serial) if serial is not None else nullcontext()
            with serial as nsh:
                # Then power on and connect GDB to get the full boot log
                pwr.on()
                yield nsh
        finally:
            if not keep_power_on:
                pwr.off(delay=0)

# -----------------------------------------------------------------------------
def _arguments(description, modifier=None):
    import argparse, emdbg
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--px4-dir",
        default=".",
        type=Path,
        help="The PX4 root directory you are working on.")
    parser.add_argument(
        "--target",
        default="px4_fmu-v5x",
        help="The target you want to debug.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--jlink",
        default=False,
        action="store_true",
        help="Use a J-Link debug probe")
    group.add_argument(
        "--stlink",
        default=False,
        action="store_true",
        help="Use an STLink debug probe")
    group.add_argument(
        "--orbtrace",
        default=False,
        action="store_true",
        help="Use an ORBtrace mini debug probe")
    group.add_argument(
        "--remote",
        help="Connect to a remote GDB server: 'IP:PORT'")
    group.add_argument(
        "--coredump",
        type=Path,
        help="Inspect a GDB coredump or PX4 hardfault log.")
    parser.add_argument(
        "--ui",
        default="cmd",
        choices=["tui", "gdbgui", "cmd", "batch"],
        help="The user interface you want to use.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level.")
    parser.add_argument(
        "-ex",
        dest="commands",
        action="append",
        help="Extra GDB commands.")
    if modifier: modifier(parser)
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)
    backend = args.remote
    if args.stlink: backend = "stlink"
    if args.jlink: backend = "jlink"
    if args.orbtrace: backend = "orbtrace"
    if args.coredump: backend = args.coredump
    return args, backend


if __name__ == "__main__":
    args, backend = _arguments("Debug FMU")

    with debug(args.px4_dir, args.target, ui=args.ui, commands=args.commands,
               backend=backend) as gdb_call:
        exit(gdb_call)
