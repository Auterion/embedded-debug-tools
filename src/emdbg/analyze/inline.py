# Copyright (c) 2024, Alexander Lerach
# Copyright (c) 2024, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from collections import defaultdict
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

LOGGER = logging.getLogger("flash:inline")


# -----------------------------------------------------------------------------
class InlinedInstance:
    """
    See :class:`InlinedFunction`.
    """
    def __init__(self, file_name: str, file_line: int, size: int) -> None:
        """
        :param file_name: file where the function is inlined to.
        :param file_line: line within the file where the function is inlined.
        :param size: amount of flash used by the inlined function in this instance.
        """
        self.file_name = file_name
        self.file_line = file_line
        self.size = size


# -----------------------------------------------------------------------------
class InlinedFunction:
    """
    The :class:`InlinedFunction` represents a function that is inlined into different callers.
    It contains a list of :class:`InlinedInstance` which represent the instance that this function is inlined into.
    """
    def __init__(self, file_name: str, file_line: int, total_size: int, inlined_instances: list[InlinedInstance]) -> None:
        """
        :param file_name: file where the inline function is declared.
        :param file_line: line within the file where the inline function is declared.
        :param total_size: total amount of flash used due to this method being inline.
        :param inlined_instances: list of instances where this function is inlined to.
        """
        self.inlined_instances = inlined_instances
        self.file_name = file_name
        self.file_line = file_line
        self.total_size = total_size

    def print(self, console: Console, num_of_instances: int, total_size: int) -> str:
        """
        Prints the inlined function and its instances to the console in an easy-to-read format.

        :param console: console to print the output to.
        :param num_of_instances: the number of inlined instances to print. A value of `0` causes all to be displayed.
        ;param total_size: total amount of FLASH used by inlined functions. Used to calculate the percentage caused by this inlined function.
        """
        console.print(f"{self.file_name}:{self.file_line} -- Total Size: {self.total_size} ({(self.total_size / total_size * 100):.2f}%)")

        table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
        table.add_column("File name")
        table.add_column("File line")
        table.add_column("Size")
        table.add_column("%")

        for i, inlined_instance in enumerate(self.inlined_instances):
            if i < num_of_instances or num_of_instances == 0:
                table.add_row(inlined_instance.file_name, str(inlined_instance.file_line),
                              str(inlined_instance.size), "{:.2f}".format(inlined_instance.size / self.total_size * 100))
            else:
                table.add_row("...", "...", "...")
                break

        console.print(table)


# -----------------------------------------------------------------------------
class AnalysisResult:
    """
    The class :class:`AnalysisResult` represents the result of an inline analysis performed using :class:`InlineAnalyzer`

    :param inlined_savings_list: inlined functions with more than one instance. These allow for potential FLASH savings.
    :param inlined_no_savings_list: inlined functions with one instance.
    :param savings_total_size: overall FLASH size used by inlined functions with more than one instance.
    :param no_savings_total_size: overall FLASH size used by inlined functions with one instance.
    """
    def __init__(self, inlined_savings_list: list[InlinedFunction], inlined_no_savings_list: list[InlinedFunction],
                savings_total_size: int, no_savings_total_size: int) -> None:
        self.inlined_savings_list = inlined_savings_list
        self.inlined_no_savings_list = inlined_no_savings_list
        self.savings_total_size = savings_total_size
        self.no_savings_total_size = no_savings_total_size


# -----------------------------------------------------------------------------
class InlineAnalyzer:
    """
    Analyzes an ELF file and DWARF debugging data to identify inline functions and the instances where they are inlined to.
    This allows to identify options for a space-time tradeoff.
    """
    def __init__(self) -> None:
        self._raw_inlined_functions = defaultdict(list)

    def get_inlined_functions(self, file_name: str) -> AnalysisResult:
        """
        Returns the identified :class:`InlinedFunction` in the given ELF file.
        This is only possible if DWARF debugging data is available which contains debug ranges and line program.

        :param file_name: path to the ELF file to analyze.

        :return: on success, a :class:`AnalysisResult` is returned. In case of errors an exception is raised.

        :raises ValueError: if the debugging data is not sufficient of the analysis.
        """
        logging.info(f"Processing file: {file_name}")
        self._raw_inlined_functions.clear()

        with open(file_name, "rb") as f:
            elf_file = ELFFile(f)

            if not elf_file.has_dwarf_info():
                raise ValueError(f"{file_name} has no DWARF info.")

            dwarf_info = elf_file.get_dwarf_info()
            range_lists = dwarf_info.range_lists()

            if range_lists is None:
                raise ValueError(f"{file_name}: DWARF info is missing debug ranges.")

            for CU in dwarf_info.iter_CUs():
                line_program = dwarf_info.line_program_for_CU(CU)

                if line_program is None:
                    logging.warning("CU @ {CU.cu_offset} DWARF info is missing line program. Skipping CU.")
                    continue

                top_die = CU.get_top_DIE()
                self.__die_get_inlined_rec(top_die, line_program, range_lists)
        return self.__raw_inlined_to_output()

    def __die_get_inlined_rec(self, die: DIE, line_program: LineProgram, range_lists: RangeLists) -> None:
        """
        Recursively traverse all DIEs of a given top DIE and extract information about inlined functions.

        :param die: DIE to be processed. Is gathered recursively after passing a top DIE.
        :param line_program: :class:`LineProgram` extracted from the DWARF debugging data.
        :param range_lists: :class:`RangeLists` extracted from the DWARF debugging data.
        """
        if die.tag == "DW_TAG_inlined_subroutine" and {"DW_AT_call_file"} <= die.attributes.keys():
            call_file = self.__get_file_name(die.attributes["DW_AT_call_file"].value, line_program)
            call_line = die.attributes["DW_AT_call_line"].value
            size = self.__get_size(die, range_lists)

            decl_die = self.__resolve_die_ref(die, die.cu.cu_offset + die.attributes["DW_AT_abstract_origin"].value)

            if {"DW_AT_decl_file", "DW_AT_decl_line"} <= decl_die.attributes.keys():
                decl_file = self.__get_file_name(decl_die.attributes["DW_AT_decl_file"].value, line_program)
                decl_line = decl_die.attributes["DW_AT_decl_line"].value

                called_function = InlinedInstance(call_file, call_line, size)
                self._raw_inlined_functions[(decl_file, decl_line)].append(called_function)

        # Recurse into the DIE children
        for child in die.iter_children():
                self.__die_get_inlined_rec(child, line_program, range_lists)

    def __get_file_name(self, file_idx: int, line_program: LineProgram) -> str:
        """
        Returns a file name given a DIE file index. To perform this mapping the line program is required.

        :param file_idx: DIE file index for which the file name shall be returned.
        :param line_program: :class:`LineProgram` extracted from the DWARF debugging data.

        :return: the file name for the given DIE file index. This will include the full path if the line program
                 contains the relevant data. Otherwise, only the file name without path will be returned.
        """
        lp_header = line_program.header
        file_entries = lp_header["file_entry"]
        file_entry = file_entries[file_idx - 1]
        dir_index = file_entry["dir_index"]

        if dir_index == 0:
            return file_entry.name.decode()

        directory = lp_header["include_directory"][dir_index - 1]
        return posixpath.join(directory, file_entry.name).decode()

    def __get_size(self, die: DIE, range_lists: RangeLists) -> int:
        """
        Returns the size required by the given DIE. The function will try different methods to get the size depending on the
        attributes being present in the DIE. If none of the methods are successful, `0` will be returned.

        :param die: DIE for which the size shall be returned.
        :param range_lists: :class:`RangeLists` extracted from the DWARF debugging data.

        :return: on success, the size of the DIE. Otherwise, `0` will be returned.
        """
        if {"DW_AT_high_pc"} <= die.attributes.keys():
            return die.attributes["DW_AT_high_pc"].value + 1
        if {"DW_AT_ranges"} <= die.attributes.keys():
            range_list = range_lists.get_range_list_at_offset(die.attributes["DW_AT_ranges"].value)
            size = 0
            for entry in range_list:
                if isinstance(entry, RangeEntry):
                    size = size + (entry.end_offset - entry.begin_offset) + 1
            return size
        return 0

    def __resolve_die_ref(self, die: DIE, ref_addr: int) -> DIE:
        """
        Given a DIE containing a reference address, the DIE referenced by that address will be returned.

        :param die: DIE containing a reference address to be resolved.
        :param ref_addr: reference address pointing to another DIE.

        :return: referenced DIE.
        """
        return die.cu.get_DIE_from_refaddr(ref_addr)

    def __raw_inlined_to_output(self) -> AnalysisResult:
        """
        Performs post-processing on the gathered data about inlined functions to bring it into an easy-to-use format.
        This includes wrapping the data into classes, grouping into inlined functions with and without FLASH saving potential
        and sorting by the amount of FLASH used.

        :return: a :class:`AnalysisResult`.
        """
        inlined_savings_list = []
        inlined_no_savings_list = []
        savings_total_size = 0
        no_savings_total_size = 0

        for (decl_file, decl_line) in self._raw_inlined_functions:
            inlined_instances = []
            total_size = 0

            for inlined_instance in self._raw_inlined_functions[(decl_file, decl_line)]:
                inlined_instances.append(inlined_instance)
                total_size = total_size + inlined_instance.size
            inlined_function = InlinedFunction(decl_file, decl_line, total_size, inlined_instances)

            if len(inlined_instances) > 1:
                inlined_savings_list.append(inlined_function)
                savings_total_size = savings_total_size + total_size
            else:
                inlined_no_savings_list.append(inlined_function)
                no_savings_total_size = no_savings_total_size + total_size

        inlined_savings_list.sort(key=lambda x: x.total_size, reverse=True)
        inlined_no_savings_list.sort(key=lambda x: x.total_size, reverse=True)
        return AnalysisResult(inlined_savings_list, inlined_no_savings_list, savings_total_size, no_savings_total_size)


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
        "--all",
        action="store_true",
        default=False,
        help="Include inlined functions that don't offer FLASH saving potential, i.e. functions that are only inlined once."
    )

    args = parser.parse_args()

    console = Console()
    inline_analyzer = InlineAnalyzer()
    analysis_result = inline_analyzer.get_inlined_functions(args.file)

    for i, inlined_function in enumerate(analysis_result.inlined_savings_list):
        if i < args.n or args.n == 0:
            inlined_function.print(console, args.m, analysis_result.savings_total_size)
            console.print("")
        else:
            console.print("[...]")
            break

    if args.all:
        for i, inlined_function in enumerate(analysis_result.inlined_no_savings_list):
            if i < args.n or args.n == 0:
                inlined_function.print(console, args.m, analysis_result.no_savings_total_size)
                console.print("")
            else:
                console.print("[...]")
                break

    console.print(f"Total saveable space: {analysis_result.savings_total_size}")

    if args.all:
        console.print(f"Total non-saveable space: {analysis_result.no_savings_total_size}")
