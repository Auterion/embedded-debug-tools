# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: fmu.md
"""

import time
from pathlib import Path
from contextlib import contextmanager, nullcontext
import emdbg


class Fmu:
    """
    FMU test bench with optional nsh, power, and logic analyzer attachements.
    """
    DBGMCU_CONFIG = [
        "set *0xE0042008 = 0xffffffff",
        "set *0xE004200C = 0xffffffff"
    ]
    MCU_MEMORIES = [
        (0x20000000, 0x00080000), # SRAM1-3
        (0x40010424, 4), # HRT uptime
    ]

    def __init__(self, elf: Path,
                 gdb: "emdbg.debug.remote.gdb.Interface",
                 nsh: "emdbg.serial.protocol.Nsh" = None,
                 power: "emdbg.power.base.Base" = None,
                 io: "emdbg.io.digilent.Digilent" = None):
        self.elf = elf
        self.gdb = gdb
        """The remote GDB access interface object"""
        self.nsh = nsh
        """The NSH protocol controller"""
        self.power = power
        """The power relay controlling the FMU"""
        self.io = io
        """The Digilent Scope"""

    def _init(self):
        self.gdb.interrupt_and_wait()
        for cmd in self.DBGMCU_CONFIG:
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

    def coredump(self, filename: str = None):
        """
        Dumps the FMU core for later analysis with CrashDebug (see
        `emdbg.debug.crashdebug`).

        :param filename: Default `coredump_{datetime}.txt`.
        """
        with self.gdb.interrupt_continue():
            if False:
                # Connection is remote, therefore we must use slower RPyC interface
                emdbg.debug.px4.coredump(self.gdb, self.MCU_MEMORIES, filename)
            else:
                # Executing directly on the GDB process is *significantly* faster!
                if filename: filename = f"--file '{filename}'"
                memories = [f"--memory {m[0]}:{m[1]}" for m in self.MCU_MEMORIES]
                self.gdb.execute(f"px4_coredump {' '.join(memories)} {filename or ''}")

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


def px4_config(px4_directory: Path, target: Path, commands: list[str] = None,
               ui: str = None, speed: int = 16000, backend: str = None):
    if "fmu-v5x" in target:
        device = "STM32F765II"
        svd = "STM32F7x5.svd"
        config = "fmu_v5x.cfg"
    elif "fmu-v6x" in target:
        device = "STM32H753II"
        svd = "STM32H753x.svd"
        config = "fmu_v6x.cfg"
    else:
        raise ValueError(f"Unknown device for '{target}'!")

    data_dir = Path(__file__).parent.resolve() / "data"

    if backend == "openocd":
        backend = emdbg.debug.OpenOcdBackend(config=[data_dir / config])
    elif backend == "jlink":
        backend = emdbg.debug.JLinkBackend(device, speed)
    elif ":" in backend:
        backend = emdbg.debug.ProbeBackend(backend)
    else:
        raise ValueError(f"Unknown backend '{backend}'. Use 'openocd', 'jlink' or 'IP:PORT'!")

    px4_dir = Path(px4_directory).absolute().resolve()
    # script_dir = px4_dir / f"platforms/nuttx/Debug"

    svd = data_dir / svd
    elf = px4_dir / f"build/{target}_default/{target}_default.elf"
    cmds = [f"dir {px4_dir}", f"source {data_dir}/fmu.gdb",
            f"source {data_dir}/orbuculum.gdb",
            f"python px4._TARGET='{target.lower()}'"]
    if ui is not None:
        cmds += Fmu.DBGMCU_CONFIG + ["python px4.restart_system_load_monitor(gdb)"]
    cmds += (commands or [])

    return backend, elf, svd, cmds


# -----------------------------------------------------------------------------
@contextmanager
def debug(px4_directory: Path, target: Path, serial: str = None,
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
    :param backend: "openocd", "jlink", or "IP:PORT" for a GDB server on another machine.

    :return: A configured test bench with the latest firmware.
    """
    backend, elf, svd, cmds = px4_config(px4_directory, target, commands, ui,
                                         backend=backend or "openocd")

    with (nullcontext() if power is None else power) as pwr:
        try:
            if ui is not None:
                # Manual mode that only connects the debugger (blocking)
                if power: pwr.on()
                yield emdbg.debug.gdb.call(backend, elf, commands=cmds, ui=ui, svd=svd)
            else:
                # Turn off, then connect the serial
                if power: pwr.off()
                serial = emdbg.serial.nsh(serial) if serial is not None else nullcontext()
                scope = emdbg.io.analog_discovery(digilent) if digilent is not None else nullcontext()
                with serial as nsh, scope as io:
                    # Then power on and connect GDB to get the full boot log
                    if power: pwr.on()
                    gdb_call = emdbg.debug.gdb.call_rpyc if with_rpyc else emdbg.debug.gdb.call_mi
                    debugger = gdb_call(backend, elf, commands=cmds, svd=svd)
                    with debugger as gdb:
                        bench = _FmuClass(elf, gdb, nsh, pwr, io)
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
if __name__ == "__main__":
    import argparse, emdbg

    parser = argparse.ArgumentParser(description="Debug FMU")
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
        "--openocd",
        default=False,
        action="store_true",
        help="Use an OpenOCD debug probe")
    group.add_argument(
        "--remote",
        help="Connect to a remote GDB server: 'IP:PORT'")
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
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)
    backend = args.remote
    if args.openocd: backend = "openocd"
    if args.jlink: backend = "jlink"

    with debug(args.px4_dir, args.target, ui=args.ui, commands=args.commands,
               backend=backend) as gdb_call:
        exit(gdb_call)
