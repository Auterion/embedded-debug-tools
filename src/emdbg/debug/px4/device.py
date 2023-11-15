# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from . import utils
from dataclasses import dataclass
from .base import Base
from functools import cached_property
from pathlib import Path
import re, time
import rich.box
from rich.text import Text
from rich.table import Table


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
            0x1007: "4",
            0x2001: "X",
            0x2003: "Y",
        }.get(self.rev, "")

    @cached_property
    def _IDCODE_DEVICE(self):
        return {
            0x0415: "STM32L47/L48xx",
            0x0451: "STM32F76xx, STM32F77xx",
            0x0450: "STM32H742, STM32H743/753, STM32H750",
            0x0483: "STM32H723/733, STM32H725/735, STM32H730",
        }.get(self.devid, "Unknown")

    @cached_property
    def _GPIOS(self):
        return {
            0x0415: list(range(0x4800_0000, 0x4800_2000, 0x400)),
            # FMUv5x/v6x don't use ports J and K
            0x0451: list(range(0x4002_0000, 0x4002_2001, 0x400)),
            0x0450: list(range(0x5802_0000, 0x5802_2001, 0x400)),
            0x0483: list(range(0x5802_0000, 0x5802_2C01, 0x400)),
        }.get(self.devid, [])

    @cached_property
    def _SYSTEM_MEMORIES(self):
        mems = [(0xE000_0000, 0x10_0000)]
        mems += {
            0x0415: [(0x1FFF_7500, 0x100)],
            0x0451: [(0x1FF0_F420, 0x100), (0x1FFF_7B00, 0x100)],
            **dict.fromkeys([0x0450, 0x0483],
                    [(0x1FF1_E800, 0x100), (0x58000524, 4)])
        }.get(self.devid, [])
        return mems

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
            0x0415: [
                (0x1000_0000, 0x20000), # SRAM2
                (0x2000_0000, 0x20000), # SRAM1
            ],
            0x0451: [
                # (0x0000_0000, 0x04000), # ITCM
                (0x2000_0000, 0x80000), # DTCM, SRAM1, SRAM2
            ],
            **dict.fromkeys([0x0450, 0x0483], [
                # (0x0000_0000, 0x10000), # ITCM
                (0x2000_0000, 0x20000), # DTCM
                (0x2400_0000, 0x80000), # AXI_SRAM
                (0x3000_0000, 0x48000), # SRAM1, SRAM2, SRAM3
                (0x3800_0000, 0x10000), # SRAM4
                (0x3880_0000, 0x01000), # Backup SRAM
                (0x5C00_1000, 4),       # IDCODE
            ]),
        }.get(self.devid, [])
        mems += self._PERIPHERALS
        mems += self._SYSTEM_MEMORIES
        return sorted(mems)

    @cached_property
    def _SVD_FILE(self):
        return {
            # 0x0415: Path(__file__).parents[1] / "data/STM32L4x6.svd",
            0x0451: Path(__file__).parents[1] / "data/STM32F765.svd",
            0x0450: Path(__file__).parents[1] / "data/STM32H753.svd",
            # 0x0483: Path(__file__).parents[1] / "data/STM32H7x3.svd",
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
        if self._hrt_base is None: return 0
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
                otyper, idr, odr, lockr = _1v(1), _1v(4), _1v(5), _1v(7)
                afr = ((gper[9] << 32 | gper[8]) >> ii*4) & 0xf
                g = self.Gpio(port, ii, moder, otyper, speedr, pupdr, idr, odr, lockr, afr)
                result.append(g)
        return result

    def coredump(self, memories: list[tuple[int, int]] = None, with_flash: bool = False) -> tuple[str, int]:
        """
        Reads the memories and registers and returns them as a formatted string
        that is compatible with CrashDebug (see `emdbg.debug.crashdebug`).

        :param memories: list of memory ranges (start, size) to dump
        :param with_flash: also dump the entire non-volatile storage
        :return: coredump formatted as string and coredump size
        """
        if memories is None:
            memories = self._MEMORIES
        if with_flash and self.flash_size:
            memories += [(0x0800_0000, self.flash_size)]
        lines = []
        total_size = 0
        for addr, size in memories:
            try:
                data = self.read_memory(addr, size).cast("I")
                total_size += size
            except Exception as e:
                print(f"Failed to read whole range [{addr:#x}, {addr+size:#x}]! {e}")
                data = []
                for offset in range(0, size, 4):
                    try:
                        data.append(self.read_memory(addr + offset, 4).cast("I")[0])
                        total_size += 4
                    except Exception as e:
                        print(f"Failed to read uint32_t {addr+offset:#x}! {e}")
                        data.append(0)
                        continue
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
    def flash_size(self) -> int:
        """The FLASH size in bytes"""
        addr = {
            0x0415: 0x1FFF_75E0,
            0x0451: 0x1FF0_F442,
            0x0450: 0x1FF1_E880,
            0x0483: 0x1FF1_E880,
        }.get(self.devid)
        if addr is None: return 0
        return self.read_uint(addr, 2) * 1024

    @cached_property
    def line(self) -> str:
        """The device family and name"""
        if self.devid == 0x0483:
            return self.read_string(0x1FF1_E8C0, length=4)[::-1]
        return self._IDCODE_DEVICE

    @cached_property
    def uid(self) -> int:
        """The device's unique identifier as a big integer"""
        addr = {
            0x0415: 0x1FFF_7590,
            0x0451: 0x1FF0_F420,
            0x0450: 0x1FF1_E800,
            0x0483: 0x1FF1_E800,
        }.get(self.devid)
        if addr is None: return 0
        return int.from_bytes(self.read_memory(addr, 3*4).tobytes(), "little")

    @cached_property
    def package(self) -> str:
        """The device package"""

        if self.devid == 0x0415:
            return {
                0b00000: "LQFP64",
                0b00010: "LQFP100",
                0b00011: "UFBGA132",
                0b00100: "LQFP144, UFBGA144, WLCSP72, WLCSP81 or WLCSP86",
                0b10000: "UFBGA169, WLCSP115",
                0b10001: "WLCSP100",
            }.get(self.read_uint(0x1FFF_7500, 1) & 0x1f, "Reserved")
        if self.devid == 0x0451:
            return {
                0b111: "LQFP208 or TFBGA216",
                0b110: "LQFP208 or TFBGA216",
                0b101: "LQFP176",
                0b100: "LQFP176",
                0b011: "WLCSP180",
                0b010: "LQFP144 ",
                0b001: "LQFP100",
            }.get(self.read_uint(0x1FFF_7BF1, 1) & 0x7, "Reserved")
        if self.devid == 0x0450:
            return {
                0b0000: "LQFP100",
                0b0010: "TQFP144",
                0b0101: "TQFP176/UFBGA176",
                0b1000: "LQFP208/TFBGA240",
            }.get(self.read_uint(0x58000524, 1) & 0xf, "All pads enabled")
        if self.devid == 0x0483:
            return {
                0b0000: "VFQFPN68 Industrial",
                0b0001: "LQFP100 Legacy / TFBGA100 Legacy",
                0b0010: "LQFP100 Industrial",
                0b0011: "TFBGA100 Industrial",
                0b0100: "WLCSP115 Industrial",
                0b0101: "LQFP144 Legacy",
                0b0110: "UFBGA144 Legacy",
                0b0111: "LQFP144 Industrial",
                0b1000: "UFBGA169 Industrial",
                0b1001: "UFBGA176+25 Industrial",
                0b1010: "LQFP176 Industrial",
            }.get(self.read_uint(0x58000524, 1) & 0xf, "All pads enabled")
        return "?"

    @cached_property
    def devid(self) -> int:
        """The STM32-specific device id part of DBG->IDCODE"""
        return self.idcode & 0xfff

    @cached_property
    def rev(self) -> int:
        """The STM32-specific revision part of DBG->IDCODE"""
        return self.idcode >> 16


def discover(gdb) -> Table:
    """
    Reads the device identifier registers and outputs a human readable string if possible.
    :return: description string
    """
    dev = Device(gdb)
    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Device")
    table.add_column("Revision")
    table.add_column("Flash")
    table.add_column("Package")
    table.add_column("UID")
    table.add_row(f"{dev.devid:#4x}: {dev.line}",
                  f"{dev.rev:#4x}: rev {dev._IDCODE_REVISION}",
                  f"{dev.flash_size//1024}kB", dev.package,
                  f"{dev.uid:x}")
    return table


def all_registers(gdb) -> dict[str, int]:
    """Return a dictionary of register name and values"""
    return Device(gdb).registers


def all_registers_as_table(gdb, columns: int = 3) -> Table:
    """
    Format the Cortex-M CPU+FPU registers and their values into a simple table.

    :param columns: The number of columns to spread the registers across.
    """
    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Name")
    table.add_column("Hexadecimal", justify="right")
    table.add_column("Decimal", justify="right")
    table.add_column("Binary", justify="right")
    for reg, value in all_registers(gdb).items():
        table.add_row(reg, f"{value:x}", str(value), f"{value:b}")
    return table


def vector_table(gdb) -> dict[int, Device.IrqNuttX]:
    """Return a dictionary of NuttX interrupt numbers and their handlers with arguments"""
    return Device(gdb).vector_table_nuttx


def vector_table_as_table(gdb, columns: int = 1) -> Table:
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
            return f"{block.function.name} {'^' * count}"
        return f"{block} ?"

    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("IRQ", justify="right")
    table.add_column("EPA")
    table.add_column("Prio")
    table.add_column("Address")
    table.add_column("Function")
    table.add_column("Argument")
    for idx, irq in vector_table(gdb).items():
        table.add_row(str(idx),
                      ("e" if irq.is_enabled else " ") +
                      ("p" if irq.is_pending else " ") +
                      ("a" if irq.is_active else " "),
                      f"{irq.priority:x}", hex(irq.handler.start),
                      _fname(irq.handler), str(irq.arg) or "",
                      style="bold blue" if irq.is_active else None)
    return table


def coredump(gdb, memories: list[tuple[int, int]] = None,
             with_flash: bool = False, filename: Path = None):
    """
    Dumps the memories and register state into a file.

    :param memories: List of (addr, size) tuples that describe which memories to dump.
    :param with_flash: Also dump the entire non-volatile storage.
    :param filename: Target filename, or `coredump_{datetime}.txt` by default.
    """
    if filename is None:
        filename = utils.add_datetime("coredump.txt")
    print("Starting coredump...", flush=True)
    start = time.perf_counter()
    output, size = Device(gdb).coredump(memories, with_flash)
    Path(filename).write_text(output)
    end = time.perf_counter()
    print(f"Dumped {size//1000}kB in {(end - start):.1f}s ({int(size/((end - start)*1000))}kB/s)")


def all_gpios_as_table(gdb, pinout: dict[str, tuple[str, str]] = None,
                       fn_filter = None, sort_by = None, columns: int = 2) -> Table:
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
    rows = []
    for gpio in Device(gdb).gpios:
        name = f"{gpio.port}{gpio.index}"
        if pinout is not None:
             list(pinout.get(name, [""]*2))
        config = "".join([["IN", "OUT", "ALT", "AN"][gpio.moder],
                          ["", "+OD"][gpio.otyper],
                          ["", "+PU", "+PD", "+!!"][gpio.pupdr],
                          ["", "+M", "+H", "+VH"][gpio.speedr],
                          ["", "+L"][gpio.lockr]])
        idr = "" if gpio.moder == 3 else ["_", "^"][gpio.idr]
        odr = ["_", "^"][gpio.odr] if gpio.moder == 1 else ""
        afr = str(gpio.afr) if gpio.moder == 2 else ""
        row = [name, config, idr, odr, afr]
        if pinout is not None:
            row += list(pinout.get(name, [""]*2))
        if fn_filter is None or fn_filter(row):
            rows.append(row)
    if sort_by is not None:
        def _sort(row):
            pinf = ord(row[0][0]) * 100 + int(row[0][1:])
            if sort_by == 0: return pinf
            if sort_by == 4: return -1 if row[4] == "" else row[4]
            if sort_by == 5: return (row[5], row[6], pinf)
            if sort_by == 6: return (row[6], row[5], pinf)
            return row[sort_by]
        rows.sort(key=_sort)

    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Pin")
    table.add_column("Config")
    table.add_column("I")
    table.add_column("O")
    table.add_column("AF", justify="right")
    if pinout is not None:
        table.add_column("Name")
        table.add_column("Function")
    for row in rows:
        table.add_row(*row)
    return table

