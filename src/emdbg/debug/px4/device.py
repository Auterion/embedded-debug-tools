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
    _HRT_CNT = 0x4001_0424
    _SCS_ICTR = 0xE000_E004
    _SCB_CPUID = 0xE000_ED00
    _SCB_VTOR = 0xE000_ED08
    _SCS_SHPR = 0xE000_ED18
    _NVIC_ISER = 0xE000_E100
    _NVIC_ISPR = 0xE000_E200
    _NVIC_IABR = 0xE000_E300
    _NVIC_IPR = 0xE000_E400

    # Try them all until one of them does not return zero
    _DBG_IDCODE = [0xE004_2000, 0x5C00_1000]

    @cached_property
    def _IDCODE_REVISION(self):
        return {
            0x1000: "A",
            0x1001: "Z",
            0x1003: "Y",
            0x2001: "X",
            0x2003: "Y",
        }.get(self.rev, "")

    @cached_property
    def _IDCODE_DEVICE(self):
        return {
            0x0451: "STM32F76xx, STM32F77xx",
            0x0450: "STM32H742, STM32H743/753, STM32H750",
        }.get(self.devid, "Unknown")

    @cached_property
    def _GPIOS(self):
        return {
            # FMUv5x/v6x don't use ports J and K
            0x0451: list(range(0x4002_0000, 0x4002_2001, 0x400)),
            0x0450: list(range(0x5802_0000, 0x5802_2001, 0x400)),
        }.get(self.devid, [])

    _SYSTEM_MEMORIES = [(0xE000_E000, 0x1100), (0xE004_2000, 4), (0x5C00_1000, 4)]

    @cached_property
    def _PERIPHERALS(self):
        if self._SVD_FILE is None: return []
        from cmsis_svd.parser import SVDParser
        device = SVDParser.for_xml_file(self._SVD_FILE).get_device()
        registers = [(per.base_address + r.address_offset,
                      per.base_address + r.address_offset + r.size//8)
                     for per in device.peripherals for r in per.registers]
        registers.sort()
        ranges = []
        cluster = 512
        current = registers[0]
        for (regl, regh) in registers[1:]:
            if (current[1] + cluster) > regh:
                current = (current[0], regh)
            else:
                ranges.append(current)
                current = (regl, regh)
        ranges.append(current)
        return [(r[0], r[1] - r[0]) for r in ranges]

    @cached_property
    def _MEMORIES(self):
        mems = {
            0x0451: [
                # (0x0000_0000, 0x04000), # ITCM
                (0x2000_0000, 0x80000), # DTCM, SRAM1, SRAM2
            ],
            0x0450: [
                # (0x0000_0000, 0x10000), # ITCM
                (0x2000_0000, 0x20000), # DTCM
                (0x2400_0000, 0x80000), # AXI_SRAM
                (0x3000_0000, 0x48000), # SRAM1, SRAM2, SRAM3
                (0x3800_0000, 0x10000), # SRAM4
                (0x3880_0000, 0x01000), # Backup SRAM
            ]
        }.get(self.devid, [])
        mems += self._PERIPHERALS
        mems += self._SYSTEM_MEMORIES
        return sorted(mems)

    @cached_property
    def _SVD_FILE(self):
        return {
            0x0451: Path(__file__).parents[2] / "bench/data/STM32F7x5.svd",
            0x0450: Path(__file__).parents[2] / "bench/data/STM32H753x.svd"
        }.get(self.devid)

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
        self._hrt_counter = self.addr_ptr(self._HRT_CNT, "uint16_t")

    @cached_property
    def _hrt_base(self):
        return self.lookup_static_symbol_in_function_ptr("base_time", "hrt_absolute_time")

    def _read_bits(self, base, index, size):
        shift = ((index * size) % 64)
        offset = (index * size) // 64
        mask = ((1 << size) - 1) << shift
        bits = self.read_memory(base + offset, 8).cast("Q")[0]
        return (bits & mask) >> shift

    def _priority(self, index):
        if index == -15: return -3
        if index == -14: return -2
        if index == -13: return -1
        if index < 0: return self._read_bits(self._SCS_SHPR, index + 16, 8)
        return self._read_bits(self._NVIC_IPR, index, 8)

    def _enabled(self, index):
        # if index < 0: return self._read_bits1(self._SCS_, index);
        return self._read_bits(self._NVIC_ISER, index, 1)

    def _pending(self, index):
        return self._read_bits(self._NVIC_ISPR, index, 1)

    def _active(self, index):
        return self._read_bits(self._NVIC_IABR, index, 1)

    @cached_property
    def uptime(self) -> int:
        """The uptime in microseconds as read from the NuttX high-resolution timer (HRT)"""
        return int(self._hrt_base.dereference() + self._hrt_counter.dereference())

    @cached_property
    def max_interrupts(self) -> int:
        """Maximum number of interrupts implemented on this device"""
        return 32 * (self.read_uint(self._SCS_ICTR, 4) + 1)

    @cached_property
    def vector_table(self) -> list[Irq]:
        """The vector table as stored inside the SCB->VTOR"""
        # SCS = 0xE000E000, SCB = 0xE000ED00, SCB->VTOR = 0xE000ED08
        # TODO: Cortex-M0 has no VTOR, Cortex-M0+ has one if implemented
        vtor = self._gdb.Value(self._SCB_VTOR).cast(self.uint32.pointer())
        vtor = vtor.dereference().cast(self.uint32.pointer())
        entries = []
        for ii in range(self.max_interrupts):
            ii -= 16
            entries.append(self.Irq(ii, self.block(vtor[ii+16]), self._priority(ii),
                                    self._enabled(ii), self._pending(ii), self._active(ii)))
        return entries

    @cached_property
    def vector_table_nuttx(self) -> dict[int, IrqNuttX]:
        """
        The index, handler and argument of the NuttX interrupt table if the
        handler is not empty and is not `irq_unexpected_isr`.
        """
        g_irqvector = self._gdb.lookup_global_symbol("g_irqvector")
        vectors = {}
        for ii, vector in enumerate(utils.gdb_iter(g_irqvector)):
            if handler := vector["handler"]:
                block = self.block(handler)
                if block.function and block.function.name == "irq_unexpected_isr":
                    continue
                ii -= 16
                vectors[ii] = self.IrqNuttX(ii, block, self._priority(ii),
                                            self._enabled(ii), self._pending(ii),
                                            self._active(ii), vector["arg"])
        return vectors

    @property
    def gpios(self) -> list[Gpio]:
        """List of GPIOs as read from the device."""
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

    def coredump(self, memories: list[tuple[int, int]] = None) -> tuple[str, int]:
        """
        Reads the memories and registers and returns them as a formatted string
        that is compatible with CrashDebug (see `emdbg.debug.crashdebug`).

        :param memories: list of memory ranges (start, size) to dump
        :return: coredump formatted as string and coredump size
        """
        if memories is None:
            memories = self._MEMORIES
        lines = []
        total_size = 0
        for addr, size in memories:
            total_size += size
            data = self.read_memory(addr, size).cast("I")
            for ii, values in enumerate(utils.chunks(data, 4, 0)):
                values = (hex(v & 0xffffffff) for v in values)
                lines.append(f"{hex(addr + ii * 16)}: {' '.join(values)}")

        for name, value in self.registers.items():
            if re.match(r"d\d+", name):
                lines.append(f"{name:<28} {float(value):<28} (raw {value & 0xffffffffffffffff:#x})")
            elif re.match(r"s\d+", name):
                lines.append(f"{name:<28} {float(value):<28} (raw {value & 0xffffffff:#x})")
            else:
                lines.append(f"{name:<28} {hex(value & 0xffffffff):<28} {int(value)}")

        return "\n".join(lines), total_size

    @cached_property
    def cpuid(self) -> int:
        """The SCB->CPUID value"""
        return self.read_uint(self._SCB_CPUID, 4)

    @cached_property
    def idcode(self) -> int:
        """The STM32-specific DBG->IDCODE value"""
        for addr in self._DBG_IDCODE:
            if idcode := (self.read_uint(addr, 4) & 0xffff0fff):
                return idcode
        return 0

    @cached_property
    def devid(self) -> int:
        """The STM32-specific device id part of DBG->IDCODE"""
        return self.idcode & 0xfff

    @cached_property
    def rev(self) -> int:
        """The STM32-specific revision part of DBG->IDCODE"""
        return self.idcode >> 16

    @cached_property
    def name(self) -> int:
        """The device name based on the DBG->IDCODE value"""
        dev = self._IDCODE_DEVICE
        if self._IDCODE_REVISION:
            dev += f" at revision {self._IDCODE_REVISION}"
        return dev

    def __repr__(self) -> str:
        return f"Device({self.architecture}, {hex(self.cpuid)}, {hex(self.devid)}, {hex(self.rev)} -> {self.name})"


def discover(gdb) -> str:
    """
    Reads the device identifier registers and outputs a human readable string if possible.
    :return: description string
    """
    dev = Device(gdb)
    return repr(dev)


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
             "a" if irq.is_active else "", f"{irq.priority:x}", hex(irq.handler.start),
             *_fname(irq.handler), irq.arg or ""]
            for idx, irq in vector_table(gdb).items()]
    # Format the table without header
    return utils.format_table(fmtstr, header, rows, columns)


def coredump(gdb, memories: list[tuple[int, int]] = None, filename: Path = None):
    """
    Dumps the memories and register state into a file.

    :param memories: List of (addr, size) tuples that describe which memories to dump.
    :param filename: Target filename, or `coredump_{datetime}.txt` by default.
    """
    if filename is None:
        filename = utils.add_datetime("coredump.txt")
    print("Starting coredump...", flush=True)
    start = time.perf_counter()
    output, size = Device(gdb).coredump(memories)
    Path(filename).write_text(output)
    end = time.perf_counter()
    print(f"Dumped {size//1000}kB in {(end - start):.1f}s ({int(size/((end - start)*1000))}kB/s)")


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

