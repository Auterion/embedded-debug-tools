# Copyright (c) 2024, Alexander Lerach
# Copyright (c) 2024, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# Analyze inline function usage

Function inlining generally is a space-time tradeoff where more inlining helps
with execution speed but increases FLASH usage. This tool helps to see which
functions are inlined where and how much FLASH usage this inlining causes.

## Command Line Interface

You can analyze the inline usage like this:

```sh
python3 -m emdbg.analyze.inline -f test.elf
```

The analysis can take some time as it has to traverse all DIEs of the DWARF data.
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import argparse
import logging
import posixpath

from elftools.elf.elffile import ELFFile
from elftools.dwarf.die import DIE
from elftools.dwarf.lineprogram import LineProgram
from elftools.dwarf.ranges import RangeEntry, RangeLists

import rich
from rich.console import Console
from rich.table import Table

_LOGGER = logging.getLogger(__name__)


def _rel_file_name(file_name: Path) -> str:
    """Return the filename relative to the CWD"""
    try: return str(Path(file_name).relative_to(Path().cwd()))
    except ValueError: return str(Path(file_name))

# -----------------------------------------------------------------------------
@dataclass
class InlinedInstance:
    """
    See `InlinedFunction`.
    """
    translation_unit: str
    """name of the translation unit this instance is used in."""
    file_name: Path
    """file where the function is inlined to."""
    file_line: int
    """line within the file where the function is inlined."""
    size: int
    """amount of flash used by the inlined function in this instance."""


# -----------------------------------------------------------------------------
@dataclass
class InlinedFunction:
    """
    The `InlinedFunction` represents a function that is inlined into different callers.
    It contains a list of `InlinedInstance` which represent the instance that this function is inlined into.
    """
    file_name: Path
    """file where the inline function is declared."""
    file_line: int
    """line within the file where the inline function is declared."""
    total_size: int
    """total amount of flash used due to this method being inline."""
    total_size_wo_overhead: int
    """total amount of flash used due to this method being inline, reduced by the function call instruction overheads."""
    inlined_instances: list[InlinedInstance]
    """list of instances where this function is inlined to."""

    def print(self, console: Console, num_of_instances: int, total_size: int, total_size_wo_overhead: int, call_overhead: int) -> str:
        """
        Prints the inlined function and its instances to the console in an easy-to-read format.

        :param console: console to print the output to.
        :param num_of_instances: the number of inlined instances to print. A value of `0` causes all to be displayed.
        :param total_size: total amount of FLASH used by inlined functions. Used to calculate the percentage caused by this inlined function.
        :param total_size_wo_overhead: total amount of FLASH used by inlined functions, reduced by the function call instruction overheads.
        :param call_overhead: expected instruction overhead caused by a function call.
        """
        console.print((
            f"{_rel_file_name(self.file_name)}:{self.file_line}"
            f" -- Total Size: {self.total_size}"
            f" ({(100 if total_size == 0 else (self.total_size / total_size * 100)):.2f}%)"
            f" -- Total Size without instruction overhead: {self.total_size_wo_overhead}"
            f" ({(100 if total_size_wo_overhead == 0 else (self.total_size_wo_overhead / total_size_wo_overhead * 100)):.2f}%)"
        ))

        table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
        table.add_column("Translation unit")
        table.add_column("File name")
        table.add_column("File line")
        table.add_column("Size")
        table.add_column("Call instruction overhead")
        table.add_column("%")

        for i, inlined_instance in enumerate(self.inlined_instances):
            if i < num_of_instances or num_of_instances == 0:
                table.add_row(_rel_file_name(inlined_instance.translation_unit), _rel_file_name(inlined_instance.file_name), str(inlined_instance.file_line),
                              str(inlined_instance.size), str(call_overhead),
                              "{:.2f}".format(100 if self.total_size == 0 else inlined_instance.size / self.total_size * 100))
            else:
                table.add_row("...", "...", "...")
                break

        console.print(table)


# -----------------------------------------------------------------------------
@dataclass
class AnalysisResult:
    """
    The class `AnalysisResult` represents the result of an inline analysis performed using `InlineAnalyzer`
    """
    inlined_savings_list: list[InlinedFunction]
    """inlined functions with more than one instance. These allow for potential FLASH savings."""
    inlined_no_savings_list: list[InlinedFunction]
    """inlined functions with one instance."""
    savings_total_size: int
    """overall FLASH size used by inlined functions with more than one instance."""
    no_savings_total_size: int
    """overall FLASH size used by inlined functions with one instance."""
    savings_total_size_wo_overhead: int
    """overall FLASH size used by inlined functions with more than one instance, reduced by function call instruction overheads."""
    no_savings_total_size_wo_overhead: int
    """overall FLASH size used by inlined functions with one instance, reduced by function call instruction overheads."""


# -----------------------------------------------------------------------------
class InlineAnalyzer:
    """
    Analyzes an ELF file and DWARF debugging data to identify inline functions and the instances where they are inlined to.
    This allows to identify options for a space-time tradeoff.

    :param call_overhead: expected instruction overhead caused by a function call.
    """
    def __init__(self, call_overhead: int):
        self._call_overhead = call_overhead
        self._raw_inlined_functions = defaultdict(list)


    def get_inlined_functions(self, file_name: str) -> AnalysisResult:
        """
        Returns the identified `InlinedFunction` in the given ELF file.
        This is only possible if DWARF debugging data is available which contains debug ranges and line program.

        :param file_name: path to the ELF file to analyze.

        :return: on success, a `AnalysisResult` is returned. In case of errors an exception is raised.

        :raises ValueError: if the debugging data is not sufficient of the analysis.
        """
        _LOGGER.info(f"Processing file: {file_name}")
        self._raw_inlined_functions.clear()

        with open(file_name, "rb") as f:
            elf_file = ELFFile(f)

            if not elf_file.has_dwarf_info():
                raise ValueError(f"{file_name} has no DWARF info.")

            dwarf_info = elf_file.get_dwarf_info()
            range_lists = dwarf_info.range_lists()

            for CU in dwarf_info.iter_CUs():
                line_program = dwarf_info.line_program_for_CU(CU)

                if line_program is None:
                    _LOGGER.warning("CU @ {CU.cu_offset} DWARF info is missing line program. Skipping CU.")
                    continue

                top_die = CU.get_top_DIE()
                self.die_get_inlined_rec(top_die, line_program, range_lists)
        return self.raw_inlined_to_output()


    def die_get_inlined_rec(self, die: DIE, line_program: LineProgram, range_lists: RangeLists):
        """
        Recursively traverse all DIEs of a given top DIE and extract information about inlined functions.

        :param die: DIE to be processed. Is gathered recursively after passing a top DIE.
        :param line_program: `LineProgram` extracted from the DWARF debugging data.
        :param range_lists: `RangeLists` extracted from the DWARF debugging data.
        """
        if die.tag == "DW_TAG_inlined_subroutine" and {"DW_AT_call_file"} <= die.attributes.keys():
            call_file = self.get_file_name(die.attributes["DW_AT_call_file"].value, line_program)
            call_line = die.attributes["DW_AT_call_line"].value
            size = self.get_size(die, range_lists)

            decl_die = self.resolve_die_ref(die, die.cu.cu_offset + die.attributes["DW_AT_abstract_origin"].value)

            if {"DW_AT_decl_file", "DW_AT_decl_line"} <= decl_die.attributes.keys():
                decl_file = self.get_file_name(decl_die.attributes["DW_AT_decl_file"].value, line_program)
                decl_line = decl_die.attributes["DW_AT_decl_line"].value
                translation_unit_name = self.get_translation_unit_name(die)

                called_function = InlinedInstance(translation_unit_name, call_file, call_line, size)
                self._raw_inlined_functions[(decl_file, decl_line)].append(called_function)

        # Recurse into the DIE children
        for child in die.iter_children():
                self.die_get_inlined_rec(child, line_program, range_lists)


    def get_file_name(self, file_idx: int, line_program: LineProgram) -> Path:
        """
        Returns a file name given a DIE file index. To perform this mapping the line program is required.

        :param file_idx: DIE file index for which the file name shall be returned.
        :param line_program: `LineProgram` extracted from the DWARF debugging data.

        :return: the file name for the given DIE file index. This will include the full path if the line program
                 contains the relevant data. Otherwise, only the file name without path will be returned.
        """
        lp_header = line_program.header
        file_entries = lp_header["file_entry"]
        file_entry = file_entries[file_idx - 1]
        dir_index = file_entry["dir_index"]

        if dir_index == 0:
            return Path(file_entry.name.decode())

        directory = lp_header["include_directory"][dir_index - 1]
        return Path(directory.decode()) / file_entry.name.decode()

    def get_translation_unit_name(self, die: DIE) -> str:
        """
        Returns the name of the translation unit the given DIE is contained in. If the name can't be retrieved,
        an empty string will be returned.

        :param die: DIE for which the translation unit name shall be returned.

        :return: on success, name of the translation unit. Otherwise, an empty string will be returned.
        """
        cu = self.resolve_die_ref(die, die.cu.cu_die_offset)

        if {"DW_AT_name"} <= cu.attributes.keys():
            return cu.attributes["DW_AT_name"].value.decode()
        else:
            return ""

    def get_size(self, die: DIE, range_lists: RangeLists) -> int:
        """
        Returns the size required by the given DIE. The function will try different methods to get the size depending on the
        attributes being present in the DIE. If none of the methods are successful, `0` will be returned.

        :param die: DIE for which the size shall be returned.
        :param range_lists: `RangeLists` extracted from the DWARF debugging data.

        :return: on success, the size of the DIE. Otherwise, `0` will be returned.
        """
        if {"DW_AT_high_pc"} <= die.attributes.keys():
            return die.attributes["DW_AT_high_pc"].value
        if {"DW_AT_ranges"} <= die.attributes.keys():
            if range_lists is None:
                raise ValueError(f"DWARF info is missing debug ranges, which is required for DIE: {die}.")

            range_list = range_lists.get_range_list_at_offset(die.attributes["DW_AT_ranges"].value)
            size = 0
            for entry in range_list:
                if isinstance(entry, RangeEntry):
                    size = size + (entry.end_offset - entry.begin_offset)
            return size
        return 0


    def resolve_die_ref(self, die: DIE, ref_addr: int) -> DIE:
        """
        Given a DIE containing a reference address, the DIE referenced by that address will be returned.

        :param die: DIE containing a reference address to be resolved.
        :param ref_addr: reference address pointing to another DIE.

        :return: referenced DIE.
        """
        return die.cu.get_DIE_from_refaddr(ref_addr)


    def raw_inlined_to_output(self) -> AnalysisResult:
        """
        Performs post-processing on the gathered data about inlined functions to bring it into an easy-to-use format.
        This includes wrapping the data into classes, grouping into inlined functions with and without FLASH saving potential
        and sorting by the amount of FLASH used.

        :return: a `AnalysisResult`.
        """
        inlined_savings_list = []
        inlined_no_savings_list = []

        savings_total_size = 0
        no_savings_total_size = 0
        savings_total_size_wo_overhead = 0
        no_savings_total_size_wo_overhead = 0

        for (decl_file, decl_line) in self._raw_inlined_functions:
            inlined_instances = []
            total_size = 0

            for inlined_instance in self._raw_inlined_functions[(decl_file, decl_line)]:
                inlined_instances.append(inlined_instance)
                total_size = total_size + inlined_instance.size
            total_size_wo_overhead = max(total_size - (len(inlined_instances) * self._call_overhead), 0)
            inlined_function = InlinedFunction(decl_file, decl_line, total_size, total_size_wo_overhead, inlined_instances)

            if len(inlined_instances) > 1:
                inlined_savings_list.append(inlined_function)
                savings_total_size = savings_total_size + total_size
                savings_total_size_wo_overhead = savings_total_size_wo_overhead + total_size_wo_overhead
            else:
                inlined_no_savings_list.append(inlined_function)
                no_savings_total_size = no_savings_total_size + total_size
                no_savings_total_size_wo_overhead = no_savings_total_size_wo_overhead + total_size_wo_overhead

        inlined_savings_list.sort(key=lambda x: x.total_size_wo_overhead, reverse=True)
        inlined_no_savings_list.sort(key=lambda x: x.total_size_wo_overhead, reverse=True)
        return AnalysisResult(inlined_savings_list, inlined_no_savings_list, savings_total_size, no_savings_total_size,
                              savings_total_size_wo_overhead, no_savings_total_size_wo_overhead)


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inline function analyzer to identify potential FLASH savings.")
    parser.add_argument(
        "-f",
        dest="file",
        help="Path to the ELF file to analyze",
        required=True
    )
    parser.add_argument(
        "-n",
        help="Number of inlined functions to display. The default value of 0 causes all inlined functions to be displayed.",
        type=int,
        default=0
    )
    parser.add_argument(
        "-m",
        help="Number of inline function instances to show for each inlined function. The default value of 0 causes all instances to be displayed.",
        type=int,
        default=0
    )
    parser.add_argument(
        "--overhead",
        help="Expected instruction overhead caused by a function call, and therefore needs to be removed from the saveable space. This should include at least one branch instruction.",
        type=int,
        default=8
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Include inlined functions that don't offer FLASH saving potential, i.e. functions that are only inlined once."
    )

    args = parser.parse_args()

    console = Console()
    inline_analyzer = InlineAnalyzer(args.overhead)
    analysis_result = inline_analyzer.get_inlined_functions(args.file)

    for i, inlined_function in enumerate(analysis_result.inlined_savings_list):
        if i < args.n or args.n == 0:
            inlined_function.print(console, args.m, analysis_result.savings_total_size, analysis_result.savings_total_size_wo_overhead, args.overhead)
            console.print("")
        else:
            console.print("[...]")
            break

    if args.all:
        for i, inlined_function in enumerate(analysis_result.inlined_no_savings_list):
            if i < args.n or args.n == 0:
                inlined_function.print(console, args.m, analysis_result.no_savings_total_size, analysis_result.no_savings_total_size_wo_overhead, args.overhead)
                console.print("")
            else:
                console.print("[...]")
                break

    console.print(f"Total potentially saveable space: {analysis_result.savings_total_size}")
    console.print(f"Total potentially saveable space without instruction overhead: {analysis_result.savings_total_size_wo_overhead}")

    if args.all:
        console.print(f"Total non-saveable space: {analysis_result.no_savings_total_size}")
        console.print(f"Total non-saveable space without instruction overhead: {analysis_result.no_savings_total_size_wo_overhead}")
