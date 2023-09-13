# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import re
from pathlib import Path
from .priority import _BoostOperation

class Frame:
    """
    Parses a GDB frame of a `backtrace` or `px4_backtrace` command.
    """
    def __init__(self, description: str):
        """
        :param description: A single line of the backtrace command starting with a `#`
        """
        self.is_valid = False
        self.description = description
        if match := re.match(r"#(\d+) +(?:0x.+? in )?(.+)\((.*?)\) at (.+?):(\d+)", description):
            self.index = int(match.group(1))
            self.function_name = match.group(2)
            self.args = match.group(3)
            self.filename = match.group(4)
            self.line = match.group(5)
            self.is_valid = True
            self.function = f"{self.function_name}({self.args})"
            self.location = f"{Path(self.filename).relative_to(Path().cwd())}:{self.line}"
            self._unique_location = self.function + "\n" + self.location

    def __hash__(self) -> int:
        return hash(self._node)

    def __eq__(self, other) -> int:
        return self.function == other.function and self.filename == other.filename

    def __repr__(self) -> str:
        return self.function

    def __str__(self) -> str:
        return f"#{self.index:<2} {self.function}"


class Backtrace:
    """
    Holds the entire call chain of a `backtrace` or `px4_backtrace` command.
    """
    EDGES = {}
    COLORS = {}

    def __init__(self, description: str):
        """
        :param description: All lines of the backtrace command
        """
        self.description = description
        tasks = (re.match(r"Task=(.+)", d) for d in description.splitlines())
        tasks = [t.group(1) for t in tasks if t is not None]
        self.task = tasks[0] if tasks else None
        self.type = self.task

        frames = (Frame(d) for d in description.splitlines())
        self.frames = [f for f in frames if f.is_valid]
        self.is_valid = len(self.frames)
        if self.is_valid:
            funcs = {f.function for f in self.frames}
            for name, pattern in self.EDGES.items():
                if any(re.search(pattern, f) for f in funcs):
                    self.type = name
                    break

    def __hash__(self) -> int:
        return hash("".join(f.filename + f.function for f in self.frames))

    def __eq__(self, other) -> int:
        ours = "".join(f.filename + f.function for f in self.frames)
        others = "".join(f.filename + f.function for f in other.frames)
        return ours == others

    def __repr__(self) -> str:
        return str(self.frames)

# -----------------------------------------------------------------------------
def _fill(color):
    return {"style": "filled", "fillcolor": color}

def _bfill(color):
    return {"style": "bold,filled", "fillcolor": color}


class FileSystemBacktrace(Backtrace):
    EDGES = dict(
        READ = r"^read$",
        WRITE = r"^write$",
        FSYNC = r"^fsync$",
        UNLINK = r"^unlink$",
        LSEEK = r"^lseek$",
        OPEN = r"^open$",
        CLOSE = r"^close$",
        READDIR = r"^readdir$",
        OPENDIR = r"^opendir$",
        MOUNT = r"^mount$",
        MKDIR = r"^mkdir$",
        STAT = r"^stat$",
        IRQ = r"^stm32_sdmmc_interrupt$",
        INIT = r"^stm32_sdio_initialize$",
    )
    COLORS = {**{"^fat_.*$": _fill("LightYellow"),
                 "^mmc?sd_.*$": _fill("LightCyan"),
                 "^stm32_.*$": _fill("DarkSeaGreen"),
                 "px4::logger::": _fill("Gold"),
                 "Navigator": _fill("GreenYellow"),
                 "can": _fill("LightSalmon"),
                 "^nsh_.*": _fill("LightSkyBlue"),
                 "^(param|bson)_.*": _fill("Bisque")},
              **{pattern: _bfill("Silver") for pattern in EDGES.values()}}


class SpiBacktrace(Backtrace):
    EDGES = dict(
        READ = r"RegisterRead|FIFOReadCount",
        WRITE = r"RegisterWrite",
        PARAM = r"^param_main$",
        NSH = r"^nsh_initialize$",
    )
    COLORS = {**{pattern: _bfill("Silver") for pattern in EDGES.values()},
              **{"^(ramtron|bch|bchlib)_.*$": _fill("LightYellow"),
                 "^spi_.*$": _fill("LightCyan"),
                 "^stm32_.*$": _fill("DarkSeaGreen"),
                 "ICM20602": _fill("Gold"),
                 "BMI088": _fill("GreenYellow"),
                 "ICM42688": _fill("LightSalmon"),
                 "^nsh_.*": _fill("LightSkyBlue"),
                 "^(param|bson)_.*": _fill("Bisque")}}


class I2cBacktrace(Backtrace):
    EDGES = dict(
        TRANSFER = r"stm32_i2c_transfer",
        NSH = r"^nsh_initialize$",
        IRQ = r"^stm32_i2c_isr$",
        INIT = r"^stm32_i2c_setclock$",
    )
    COLORS = {**{"^stm32_.*$": _fill("DarkSeaGreen"),
                 "BMM150": _fill("Yellow"),
                 "IST8310": _fill("Cyan"),
                 "BMP388": _fill("Gold"),
                 "RGBLED": _fill("LightSkyBlue"),
                 "MCP23009": _fill("LightSalmon")},
              **{pattern: _bfill("Silver") for pattern in EDGES.values()}}


class CanBacktrace(Backtrace):
    EDGES = dict(
        SEND = r"CanIface::send$",
        RECEIVE = r"CanIface::receive$",
        INIT = r"CanIface::init$",
        FRAME = r"TransferListener::handleFrame$",
    )
    COLORS = {**{pattern: _bfill("Silver") for pattern in EDGES.values()},
              **{"^(ramtron|bch|bchlib)_.*$": _fill("LightYellow"),
                 "Publisher": _fill("DarkSeaGreen")}}


class UartBacktrace(Backtrace):
    EDGES = dict(
        READ = r"^read$",
        WRITE = r"^write$",
        FFLUSH = r"^fflush$",
        FPUTC = r"^fputc$",
        FPUTS = r"^fputs$",
        OPEN = r"^open$",
        SYSLOG = r"^syslog$",
        PRINTF = r"^printf$",
        IRQ = r"^irq_dispatch$",
        INIT = r"^arm_earlyserialinit$",
    )
    COLORS = {**{"^I2CSPI": _fill("LightYellow"),
                 "^(up|uart)_.*$": _fill("LightCyan"),
                 "^stm32_.*$": _fill("DarkSeaGreen"),
                 "px4::logger": _fill("Gold"),
                 "[mM]avlink": _fill("GreenYellow"),
                 "can": _fill("LightSalmon"),
                 "^nsh_.*": _fill("LightSkyBlue"),
                 "^(param|bson)_.*": _fill("Bisque")},
              **{pattern: _bfill("Silver") for pattern in EDGES.values()}}


class SemaphoreBacktrace(Backtrace):
    # EDGES = dict(
    #     RESTORE = r"^nxsem_restoreholderprio$",
    #     BOOST =  r"^nxsem_boostholderprio$",
    #     WAIT = r"^nxsem_wait$",
    #     POST = r"^nxsem_post$",
    #     INIT = r"^sem_init$",
    #     DESTROY = r"^sem_destroy$",
    #     FREE = r"^free$",
    #     MALLOC = r"^malloc$",
    #     MEMSET = r"^memset$",
    # )
    # COLORS = {pattern: _bfill("Silver") for pattern in EDGES.values()}
    def __init__(self, description: str):
        """
        :param description: All lines of the backtrace command also containing a boost trace command.
        """
        super().__init__(description)
        ops = (_BoostOperation(d) for d in description.splitlines())
        ops = [o for o in ops if o.is_valid]
        self.operation = ops[0] if ops else None
        if self.operation is not None:
            self.type = self.operation.task
        if ops and self.operation.prio_to == 255:
            if self.type is not None:
                self.type += "_255"
            else:
                self.type = "255"
