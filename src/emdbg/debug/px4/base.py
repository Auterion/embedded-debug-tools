# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import re
from . import utils
from functools import cached_property

class Base:
    """
    This base class provides basic abstractions to simplify usage of the GDB
    Python API, which can be a little verbose.

    It also provides a mechanism to invalidate cached properties whenever GDB
    stopped. This allows the use of `@cached_property` when the target is halted
    to cache expensive operations.
    """
    def __init__(self, gdb):
        self._gdb = gdb
        self._inf = gdb.selected_inferior()
        self._arch = self._inf.architecture()
        self.register_names = [r.name for r in self._arch.registers()]
        # Registering a callback for every obj makes GDB *really* slow :(
        global _CACHED_OBJECTS
        if _CACHED_OBJECTS is None:
            gdb.events.stop.connect(_invalidate_cached_properties)
            _CACHED_OBJECTS = []
        _CACHED_OBJECTS.append(self)

    def _invalidate(self):
        for key, value in self.__class__.__dict__.items():
            if isinstance(value, cached_property):
                self.__dict__.pop(key, None)

    @cached_property
    def registers(self) -> dict[str, int]:
        """All register names and unsigned values in the selected frame."""
        return {r: self.read_register(r) for r in self.register_names}

    def read_register(self, name: str) -> int:
        """:return: unsigned value of the named register in the selected frame"""
        frame = self._gdb.selected_frame()
        # This is convoluted because we need to get the raw FPU register values!
        # Otherwise they get cast from double to int, which is wrong.
        value = int(frame.read_register(name).format_string(format="x"), 16)
        return value

    def write_register(self, name: str, value: int):
        """Writes a value into the named register"""
        try:
            # casting to (void*) allows setting the FPU registers with raw!
            self._gdb.execute(f"set ${name} = (void*){int(value):#x}")
        except Exception as e:
            print(e)

    def write_registers(self, values: dict[str, int]):
        """Writes all named registers into the CPU"""
        for name, value in values.items():
            #
            if name in ["control", "faultmask", "primask"]: continue
            # GDB does not know SP, only MSP and PSP
            if name in ["sp", "r13"]:
                name = "msp"
            if name == "msp":
                self.write_register("r13", value)
            # Remove double FP registers
            if name.startswith("d"): continue
            self.write_register(name, value)

    def lookup_static_symbol_in_function(self, symbol_name: str, function_name: str) -> "gdb.Symbol | None":
        """
        Lookup a static symbol inside a function. GDB makes this complicated
        since static symbols inside functions are not accessible directly.

        :return: the symbol if found or `None`
        """
        if (function := self._gdb.lookup_global_symbol(function_name)) is None:
            return None
        function = function.value()
        function_block = self._gdb.block_for_pc(int(function.address))
        for symbol in function_block:
            if symbol.addr_class == self._gdb.SYMBOL_LOC_STATIC:
                if symbol.name == symbol_name:
                    return symbol
        return None

    def lookup_static_symbol_ptr(self, name: str) -> "gdb.Value":
        """:return: a Value to a static symbol name"""
        if symbol := self._gdb.lookup_static_symbol(name):
            return self.value_ptr(symbol)
        return None

    def lookup_global_symbol_ptr(self, name) -> "gdb.Value":
        """:return: a Value to a global symbol name"""
        if symbol := self._gdb.lookup_global_symbol(name):
            return self.value_ptr(symbol)
        return None

    def lookup_static_symbol_in_function_ptr(self, symbol_name: str, function_name: str) -> "gdb.Value | None":
        """:return: a Value to a global symbol name"""
        if symbol := self.lookup_static_symbol_in_function(symbol_name, function_name):
            return self.value_ptr(symbol)
        return None

    def value_ptr(self, symbol: "gdb.Symbol") -> "gdb.Value":
        """
        Convert a symbol into a value. This can be useful if you want to keep a
        "pointer" of the symbol, whose content is always up-to-date, rather than
        a local copy, which will never be updated again.
        """
        return self._gdb.Value(symbol.value().address).cast(symbol.type.pointer())

    def addr_ptr(self, addr: int, type: str) -> "gdb.Value":
        """Cast a memory address to a custom type."""
        return self._gdb.Value(addr).cast(self._gdb.lookup_type(type).pointer())

    def read_memory(self, address: int, size: int) -> memoryview:
        """
        Reads a block of memory and returns its content.
        See [Inferiors](https://sourceware.org/gdb/onlinedocs/gdb/Inferiors-In-Python.html).
        """
        return self._inf.read_memory(address, size)

    def write_memory(self, address: int, buffer, length: int):
        """
        Writes a block of memory to an address.
        See [Inferiors](https://sourceware.org/gdb/onlinedocs/gdb/Inferiors-In-Python.html).
        """
        self._inf.write_memory(address, buffer, length=length)

    def read_uint(self, addr: int, size: int, default=None) -> int:
        """Reads an unsigned integer from a memory address"""
        if (itype := {1: "B", 2: "H", 4: "I", 8: "Q"}.get(size)) is None:
            raise ValueError("Unsupported unsigned integer size!")
        try:
            return self.read_memory(addr, size).cast(itype)[0]
        except self._gdb.MemoryError:
            return default

    def read_int(self, addr: int, size: int, default=None) -> int:
        """Reads a signed integer from a memory address"""
        if (itype := {1: "b", 2: "h", 4: "i", 8: "q"}.get(size)) is None:
            raise ValueError("Unsupported signed integer size!")
        try:
            return self.read_memory(addr, size).cast(itype)[0]
        except self._gdb.MemoryError:
            return default

    def read_string(self, addr: int, encoding: str = None,
                    errors: str = None, length: int = None) -> str:
        """Reads a string of a fixed length, or with 0 termination"""
        kwargs = {"encoding": encoding or "ascii", "errors": errors or "ignore"}
        if length: kwargs["length"] = length
        return self.addr_ptr(addr, "char").string(**kwargs)

    def symtab_line(self, pc: int) -> "gdb.Symtab_and_line":
        """:return: the symbol table and line for a program location"""
        return self._gdb.find_pc_line(int(pc))

    def block(self, pc: int) -> "gdb.Block":
        """:return: the block for a program location"""
        return self._gdb.block_for_pc(int(pc))

    def description_at(self, addr: int) -> str | None:
        """:return: the human-readable symbol description at an address"""
        output = self._gdb.execute(f"info symbol *{int(addr)}", to_string=True)
        if match := re.search(r"(.*?) in section (.*?)", output):
            return match.group(1)
        return None

    def integer_type(self, size: int, signed: bool = True) -> "gdb.Type":
        """:return: The built-in integer type for the size in bits"""
        return self._arch.integer_type(size * 8, signed=True)

    @property
    def uint32(self) -> "gdb.Type":
        """The built-in unsigned 32-bit integer type"""
        return self.integer_type(4, False)

    @property
    def int32(self) -> "gdb.Type":
        """The built-in signed 32-bit integer type"""
        return self.integer_type(4, True)


# Single callback makes GDB much faster, so we do the loop ourselves
_CACHED_OBJECTS = None
def _invalidate_cached_properties(event):
    global _CACHED_OBJECTS
    for obj in _CACHED_OBJECTS:
        if obj: obj._invalidate()
