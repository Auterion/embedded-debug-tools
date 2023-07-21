# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import io
from pathlib import Path
from collections import defaultdict
from contextlib import redirect_stdout

from . import utils
from .device import Device


class PeripheralWatcher(Device):
    """Visualize the changes of a peripheral register map."""

    def __init__(self, gdb, filename: Path = None):
        from cmsis_svd.parser import SVDParser
        super().__init__(gdb)
        if filename is None: filename = self._SVD_FILE
        self.device = SVDParser.for_xml_file(filename).get_device()
        self._watched = {}

    def _find(self, name):
        if isinstance(name, str):
            rname = None
            if "." in name:
                name, rname = name.split(".")
            peripheral = next((p for p in self.device.peripherals if p.name == name), None)
            if peripheral is None:
                raise ValueError(f"Unknown peripheral instance '{name}'! "
                                 f"Available peripherals are {','.join(p.name for p in self.device.peripherals)}")
            if rname:
                register = next((r for r in peripheral.registers if r.name == rname), None)
                if register is None:
                    raise ValueError(f"Unknown register instance '{name}.{rname}'! "
                                     f"Available registers are {','.join(r.name for r in peripheral.registers)}")
                return [(peripheral, register)]
            return [(peripheral, register) for register in peripheral.registers]
        return name if isinstance(name, list) else [name]

    def address(self, name):
        """
        :return: A dictionary of register to address mapping.
        """
        return {(p,r): (p.base_address + r.address_offset,
                        p.base_address + r.address_offset + r.size//8)
                for p, r in self._find(name)}

    def watch(self, name: str) -> str:
        """
        Add a peripheral to the watch list.

        :param name: name of peripheral instance.
        :raises ValueError: if instance name is unknown.

        :return: difference report compared to reset values as defined in SVD.
        """
        registers = self._find(name)
        self.update(registers)
        report = self.report(registers)
        self.update(registers)
        return report

    def unwatch(self, name: str = None):
        """
        Remove a peripheral from the watch list.

        :param name: name of peripheral instance, or all watched peripheral if `None`.
        :raises ValueError: if instance name is unknown.
        """
        if name is not None:
            for register in self._find(name):
                if register in self._watched:
                    self._watched.pop(register)
        else:
            self._watched = {}

    def update(self, name: str = None):
        """
        Update all cached register values to the current values.
        Note: This performs a read from the device of all watched registers.

        :param name: name of peripheral instance, or all watched peripheral if `None`.
        :raises ValueError: if instance name is unknown.
        """
        if name is not None:
            for peripheral, register in self._find(name):
                new = (peripheral, register) not in self._watched
                addr = peripheral.base_address + register.address_offset
                value = register.reset_value if new else self.read_uint(addr, register.size // 8)
                self._watched[(peripheral, register)] = value
        else:
            for register in self._watched:
                self.update(register)

    def reset(self, name: str = None):
        """
        Update all cached registers to their reset values as defined in the
        CMSIS-SVD file.

        :param name: name of peripheral instance, or all watched peripheral if `None`.
        :raises ValueError: if instance name is unknown.
        """
        if name is not None:
            for register in self._find(name):
                self._watched.pop(register)
                self.update(register)
        else:
            registers = list(self._watched)
            for register in registers:
                self.reset(register)

    def report(self, name: str = None) -> str:
        """
        Compare the cached registers with the on-device registers and compute
        the difference.

        :param name: name of peripheral instance, or all watched peripheral if `None`.
        :raises ValueError: if instance name is unknown.
        :return: The difference report as a string with ANSI formatting.
        """
        if name is None:
            # return sum(map(self.report, self._watched.keys()))
            report = ""
            for register in self._watched:
                report += self.report(register)
            return report

        from arm_gdb.common import RegisterDef, FieldBitfieldEnum, FieldBitfield

        report = []
        addr_map = {}
        for peripheral, register in self._find(name):
            value = self._watched[(peripheral, register)]
            addr = peripheral.base_address + register.address_offset
            new_value = self.read_uint(addr, register.size // 8)

            if difference := new_value ^ value:
                fields = []
                for field in sorted(register.fields, key=lambda f: f.bit_offset):
                    # Check if difference is within mask of this bit field
                    if (difference & (((1 << field.bit_width) - 1) << field.bit_offset)):
                        fields.append(FieldBitfield(
                            field.name,
                            field.bit_offset,
                            field.bit_width,
                            field.description
                        ))
                reg = RegisterDef(
                    peripheral.name + "." + register.name,
                    register.description,
                    addr,
                    register.size // 8,
                    fields
                )

                # dump previous register values
                class CachedInferior:
                    def read_memory(self, addr, size):
                        class MemoryView:
                            def tobytes(self):
                                return value.to_bytes(size, "little")
                        return MemoryView()
                with redirect_stdout(io.StringIO()) as buffer:
                    reg.dump(CachedInferior(), include_descr=True, base=1, all=True)
                for line in buffer.getvalue().splitlines():
                    report.append(f"\033[2m- {line}\033[0m")

                # dump current register values
                inf = self._gdb.selected_inferior()
                with redirect_stdout(io.StringIO()) as buffer:
                    reg.dump(inf, include_descr=True, base=1, all=True)
                for line in buffer.getvalue().splitlines():
                    report.append(f"+ {line}")
        return "\n".join(report)
