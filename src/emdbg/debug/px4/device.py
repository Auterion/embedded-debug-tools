# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from . import utils
from dataclasses import dataclass
from .base import Base
from functools import cached_property
from pathlib import Path
import re, time


class Device(Base):
    """
    Accessors for the state of ARM Cortex-M CPU, STM32 identifiers, uptime, and
    NuttX kernel internals.
    """
    _DBG_IDCODE = 0xE004_2000
    _SCB_CPUID = 0xE000_ED00
    _SCB_VTOR = 0xE000_ED08
    _SCS_ICTR = 0xE000_E004
    _NVIC_ISER = 0xE000_E100
    _NVIC_ISPR = 0xE000_E200
    _NVIC_IABR = 0xE000_E300
    _NVIC_IPR = 0xE000_E400

    # _GPIOS = list(range(0x4002_0000, 0x4002_2801, 0x400))
    # FMUv5x/v6x don't use ports J and K
    _GPIOS = list(range(0x4002_0000, 0x4002_2001, 0x400))
    _TIM8_CNT = 0x4001_0424

    _IDCODE_MAP = {
        0x1000_0451: "STM32F7[67]xx/revA",
        0x1001_0451: "STM32F7[67]xx/revZ",
    }

    @dataclass
    class Gpio:
        port: str
        index: int
        moder: int
        otyper: int
        speedr: int
        pupdr: int
        idr: int
        odr: int
        lockr: int
        afr: int

    @dataclass
    class Irq:
        index: int
        """Index of the IRQ starting at zero"""
        handler: "gdb.Block"
        """Function handler of the IRQ"""
        priority: int
        """Priority of the IRQ"""
        is_enabled: bool
        """Is interrupt enabled"""
        is_pending: bool
        """Is interrupt pending"""
        is_active: bool
        """Is interrupt active"""

    @dataclass
    class IrqNuttX(Irq):
        arg: "gdb.Value"
        """Optional argument passed to the IRQ handler"""

    def __init__(self, gdb):
        super().__init__(gdb)
        self.architecture = self._arch.name()
        self._hrt_base = self.lookup_static_symbol_in_function_ptr("base_time", "hrt_absolute_time")
        self._hrt_counter = self.addr_ptr(self._TIM8_CNT, "uint16_t")

    def _priority(self, index):
        ipr = self.read_uint(self._NVIC_IPR + index // 4, 4)
        ipr >>= (index % 4) * 8
        return (ipr & 0xff) >> 4

    def _nvic_bit(self, base, index):
        bits = self.read_uint(base + (index // 32) * 4, 4)
        bits >>= (index % 32)
        return bits & 1

    def _enabled(self, index):
        return self._nvic_bit(self._NVIC_ISER, index)

    def _pending(self, index):
        return self._nvic_bit(self._NVIC_ISPR, index)

    def _active(self, index):
        return self._nvic_bit(self._NVIC_IABR, index)

    @cached_property
    def uptime(self) -> int:
        """:return: The uptime in microseconds as read from the NuttX high-resolution timer (HRT)"""
        return int(self._hrt_base.dereference() + self._hrt_counter.dereference())

    @cached_property
    def vector_table(self) -> list[Irq]:
        """:return: The vector table as stored inside the SCB->VTOR"""
        # ICTR describes how many interrupts are actually implemented
        max_interrupts = 32 * (self.read_uint(self._SCS_ICTR, 4) + 1)
        # SCS = 0xE000E000, SCB = 0xE000ED00, SCB->VTOR = 0xE000ED08
        # TODO: Cortex-M0 has no VTOR, Cortex-M0+ has one if implemented
        vtor = self._gdb.Value(self._SCB_VTOR).cast(self.uint32.pointer())
        vtor = vtor.dereference().cast(self.uint32.pointer())
        entries = []
        for ii in range(max_interrupts):
            entries.append(self.Irq(ii, self.block(vtor[ii]), self._priority(ii),
                                    self._enabled(ii), self._pending(ii), self._active(ii)))
        return entries

    @cached_property
    def vector_table_nuttx(self) -> dict[int, IrqNuttX]:
        """
        :return: the index, handler and argument of the NuttX interrupt table if
                 the handler is not empty and is not `irq_unexpected_isr`.
        """
        g_irqvector = self._gdb.lookup_global_symbol("g_irqvector")
        vectors = {}
        for ii, vector in enumerate(utils.gdb_iter(g_irqvector)):
            if handler := vector["handler"]:
                block = self.block(handler)
                if block.function and block.function.name == "irq_unexpected_isr":
                    continue
                vectors[ii - 16] = self.IrqNuttX(ii, block, self._priority(ii),
                                                 self._enabled(ii), self._pending(ii),
                                                 self._active(ii), vector["arg"])
        return vectors

    @property
    def gpios(self) -> list[Gpio]:
        result = []
        for jj, gper_addr in enumerate(self._GPIOS):
            port = chr(ord("A") + jj)
            gper = self.read_memory(gper_addr, 0x28).cast("I")
            for ii in range(16):
                _1v = lambda index: (gper[index] >> ii) & 0x1
                _2v = lambda index: (gper[index] >> ii*2) & 0x3
                moder, speedr, pupdr = _2v(0), _2v(2), _2v(3)
                otyper, idr, odr, lockr = _1v(1), _1v(4), _1v(5), _1v(6)
                afr = ((gper[8] << 32 | gper[7]) >> ii*4) & 0xf
                g = self.Gpio(port, ii, moder, otyper, speedr, pupdr, idr, odr, lockr, afr)
                result.append(g)
        return result

    def coredump(self, memories: list[tuple[int, int]]):
        """
        Reads the memories and registers and returns them as a formatted string
        that is compatible with CrashDebug (see `emdbg.debug.crashdebug`).
        """
        lines = []
        for addr, size in memories:
            data = self.read_memory(addr, size).cast("I")
            for ii, values in enumerate(utils.chunks(data, 4, 0)):
                values = (hex(v & 0xffffffff) for v in values)
                lines.append(f"{hex(addr + ii * 16)}: {' '.join(values)}")

        for name, value in self.registers.items():
            if re.match(r"d\d+", name):
                lines.append(f"{name:<28} {float(value):<28} (raw {value&0xffffffffffffffff:#x})")
            elif re.match(r"s\d+", name):
                lines.append(f"{name:<28} {float(value):<28} (raw {value&0xffffffff:#x})")
            else:
                lines.append(f"{name:<28} {hex(value&0xffffffff):<28} {int(value)}")

        return "\n".join(lines)

    def coredump_with_peripherals(self, memories: list[tuple[int, int]]):
        """
        Reads the memories and registers and returns them as a formatted string
        that is compatible with CrashDebug (see `emdbg.debug.crashdebug`).
        """
        from .svd import _SVD_FILES
        device = _SVD_FILES[0]
        memories.append( (start, size) )

        return
    @cached_property
    def cpuid(self) -> int:
        """:return: the SCB->CPUID value"""
        return self.read_uint(self._SCB_CPUID, 4)

    @cached_property
    def idcode(self) -> int:
        """:return: the STM32-specific DBG->IDCODE value"""
        return self.read_uint(self._DBG_IDCODE, 4) & 0xffff0fff

    @cached_property
    def devid(self) -> int:
        """:return: the STM32-specific device id part of DBG->IDCODE"""
        return self.idcode & 0xfff

    @cached_property
    def rev(self) -> int:
        """:return: the STM32-specific revision part of DBG->IDCODE"""
        return self.idcode >> 16

    @cached_property
    def name(self) -> int:
        """:return: The device name based on the DBG->IDCODE value"""
        return self._IDCODE_MAP.get(self.idcode, "Unknown")

    def __repr__(self) -> str:
        return f"Device({self.architecture}, {hex(self.cpuid)}, {hex(self.devid)}, {hex(self.rev)} -> {self.name})"



def all_registers(gdb) -> dict[str, int]:
    """Return a dictionary of register name and values"""
    return Device(gdb).registers


def all_registers_as_table(gdb, columns: int = 3) -> str:
    """
    Format the Cortex-M CPU+FPU registers and their values into a simple table.

    :param columns: The number of columns to spread the registers across.
    """
    fmtstr = "{:%d}  {:>%d}  {:>%d}"
    # Format all registers into single array
    rows = [[reg, hex(value), value] for reg, value in all_registers(gdb).items()]
    # Format the table without header
    return utils.format_table(fmtstr, None, rows, columns)


def vector_table(gdb) -> dict[int, Device.IrqNuttX]:
    """Return a dictionary of NuttX interrupt numbers and their handlers with arguments"""
    return Device(gdb).vector_table_nuttx


def vector_table_as_table(gdb, columns: int = 1) -> str:
    """
    Format the NuttX interrupts and their handlers with arguments into a simple table.

    :param columns: The number of columns to spread the interrupts across.
    """
    def _fname(block):
        count = 0
        while block and block.function is None:
            block = block.superblock
            count += 1
        if block.function:
            return "^" * count, block.function.name
        return "?", block

    fmtstr = "{:>%d} {:>%d}{:>%d}{:>%d} {:>%d}  {:>%d} = {:>%d} {:%d}  {:%d}"
    header = ["IRQ", "E", "P", "A", "P", "ADDR", "", "FUNCTION", "ARGUMENT"]
    # Format all registers into single array
    rows = [[idx, "e" if irq.is_enabled else "", "p" if irq.is_pending else "",
             "a" if irq.is_active else "", irq.priority, hex(irq.handler.start),
             *_fname(irq.handler), irq.arg or ""]
            for idx, irq in vector_table(gdb).items()]
    # Format the table without header
    return utils.format_table(fmtstr, header, rows, columns)


def coredump(gdb, memories: list[tuple[int, int]], filename: Path = None):
    """
    Dumps the memories and register state into a file.

    :param memories: List of (addr, size) tuples that describe which memories to dump.
    :param filename: Target filename, or `coredump_{datetime}.txt` by default.
    """
    if filename is None:
        filename = utils.add_datetime("coredump.txt")
    print("Starting coredump...", flush=True)
    start = time.perf_counter()
    output = Device(gdb).coredump(memories)
    Path(filename).write_text(output)
    end = time.perf_counter()
    print(f"Coredump completed in {(end - start):.1f}s")


def all_gpios_as_table(gdb, pinout: dict[str, tuple[str, str]] = None,
                       fn_filter = None, sort_by = None, columns: int = 2):
    """
    Reads the GPIO peripheral space and prints a table of the individual pin
    configuration, input/output state and alternate function. If a pinout is
    provided, the pins will be matched with their names and functions.

    Config: Condensed view with omitted defaults.
        MODER:  IN=Input, OUT=Output, ALT=Alternate Function, AN=Analog,
        OTYPER: +OD=OpenDrain, (+PP=PushPull omitted),
        PUPDR:  +PU=PullUp, +PD=PullDown, (+FL=Floating omitted),
        SPEEDR: +M=Medium, +H=High, +VH=Very High, (+L=Low omitted).

    Input (IDR), Output (ODR): _=Low, ^=High
        Input only shown for IN, OUT, and ALT.
        Output only shown for OUT.

    Alternate Function (AFR): only shown when config is ALT.
        Consult the datasheet for device-specific mapping.

    :param pinout: A map of port+index -> (name, function).
    :param pin_filter: A filter function that gets passed the entire row as a
                       list and returns `True` if row is accepted.
    :param sort_by: The name of the column to sort by: default is `PIN`.
    :param columns: The number of columns to spread the GPIO table across.
    """
    fmtstr = "{:%d}  {:%d}  {:%d} {:%d}  {:>%d}"
    header = ["PIN", "CONFIG", "I", "O", "AF"]
    if pinout is not None:
        fmtstr += "  {:%d}  {:%d}"
        header += ["NAME", "FUNCTION"]
    rows = []
    for gpio in Device(gdb).gpios:
        name = f"{gpio.port}{gpio.index}"
        if pinout is not None:
             list(pinout.get(name, [""]*2))
        config = "".join([["IN", "OUT", "ALT", "AN"][gpio.moder],
                          ["", "+OD"][gpio.otyper],
                          ["", "+PU", "+PD", "+!!"][gpio.pupdr],
                          ["", "+M", "+H", "+VH"][gpio.speedr]])
        idr = "" if gpio.moder == 3 else ["_", "^"][gpio.idr]
        odr = ["_", "^"][gpio.odr] if gpio.moder == 1 else ""
        afr = gpio.afr if gpio.moder == 2 else ""
        row = [name, config, idr, odr, afr]
        if pinout is not None:
            row += list(pinout.get(name, [""]*2))
        if fn_filter is None or fn_filter(row):
            rows.append(row)
    if sort_by:
        idx = header.index(sort_by.upper())
        def _sort(row):
            pinf = ord(row[0][0]) * 100 + int(row[0][1:])
            if idx == 0: return pinf
            if idx == 4: return -1 if row[4] == "" else row[4]
            if idx == 5: return (row[5], row[6], pinf)
            if idx == 6: return (row[6], row[5], pinf)
            return row[idx]
        rows.sort(key=_sort)
    return utils.format_table(fmtstr, header, rows, columns)

