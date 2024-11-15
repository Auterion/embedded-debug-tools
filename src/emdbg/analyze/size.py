# Copyright (c) 2024, Alexander Lerach
# Copyright (c) 2024, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from shutil import which
import argparse
import logging
import re
import subprocess

import rich
from rich.console import Console
from rich.table import Table

_LOGGER = logging.getLogger(__name__)
_BLOATY_CMD = "bloaty"


# -----------------------------------------------------------------------------
def _rel_file_name(file_path: Path) -> str:
    """Return the filename relative to the CWD."""
    try: return str(Path(file_path).relative_to(Path().cwd()))
    except ValueError: return str(Path(file_path))


# -----------------------------------------------------------------------------
def _remove_all_spaces(s: str) -> str:
    """Removes all spaces from the given string."""
    return ''.join(s.split())


# -----------------------------------------------------------------------------
def is_bloaty_installed() -> bool:
    """Checks if bloaty is installed and contained in PATH."""
    return which(_BLOATY_CMD) is not None


# -----------------------------------------------------------------------------
class SectionType(Enum):
    """
    The `SectionType` describes what kind of type a linker section is.
    """
    text = 0,
    rodata = 1,
    bss = 2,
    data = 3,
    debug = 4,
    unknown = 5


# -----------------------------------------------------------------------------
@dataclass
class Section:
    """
    The class `Section` represents a linker section.
    """
    name: str
    """name of the linker section."""
    section_type: SectionType
    """type of the linker section."""
    vm_size: int
    """VM size that the linker section uses"""
    file_size: int
    """file size that the linker section uses"""


# -----------------------------------------------------------------------------
@dataclass
class AnalysisResult:
    """
    The class `AnalysisResult` represents the result of an inline analysis performed using `SectionAnalyzer`.
    """
    file_path: Path
    """path of the file that was analyzed."""
    sections: list[Section]
    """all linker sections that were found in the analyzed file and passed the given filters."""
    total_vm_size: int
    """overall VM size that is used by all sections in the analyzed file."""
    total_file_size: int
    """overall file size that is used by all sections in the analyzed file."""

    def print(self, console: Console, overall_vm_size: int, overall_file_size: int):
        """
        Prints the analyzed file with its linker sections in an easy-to-read format.

        :param console: console to print the output to.
        :param overall_vm_size: overall VM size that is used by all sections of all analyzed files.
        :param overall_file_size: overall file size that is used by all sections of all analyzed files.
        """
        console.print((
             f"{_rel_file_name(self.file_path)} -- Total VM Size: {self.total_vm_size}"
             f" ({(100 if overall_vm_size == 0 else (self.total_vm_size / overall_vm_size * 100)):.2f}%)"
             f" -- Total File Size: {self.total_file_size}"
             f" ({(100 if overall_file_size == 0 else (self.total_file_size / overall_file_size * 100)):.2f}%)"
        ))

        table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
        table.add_column("Section")
        table.add_column("Type")
        table.add_column("VM size")
        table.add_column("File size")
        table.add_column("% (VM size)")
        table.add_column("% (File size)")

        for section in self.sections:
            table.add_row(section.name, str(section.section_type.name), str(section.vm_size), str(section.file_size),
                          "{:.2f}".format(100 if self.total_vm_size == 0 else section.vm_size / self.total_vm_size * 100),
                          "{:.2f}".format(100 if self.total_file_size == 0 else section.file_size / self.total_file_size * 100))

        console.print(table)

    def to_csv_lines(self) -> str:
        """
        Prints the analyzed file with its linker sections into the CSV format. This allows for analysis in another tool.
        """
        out = ""

        for section in self.sections:
            out = out + f"{_rel_file_name(self.file_path)},{section.name},{section.section_type.name},{section.vm_size},{section.file_size}\n"
        return out


# -----------------------------------------------------------------------------
class SectionAnalyzer:
    """
    The `SectionAnalyzer` extracts information about linker sections using bloaty.

    :param map_file_content: The contents of the map file. If `None` is passed, the output may contain sections that are removed by the linker.
    :param all_vm: Tells whether to include sections with a VM size of 0.
    :param section_filter: Regex that will be used as a filter on section names. `None` in case of no filter.
    :param type_filter: List of section types that shall be considered. Empty in case of no filters.
    """
    def __init__(self, map_file_content: str | None, all_vm: bool, section_filter: str | None, type_filter: list[str]):
        self._map_file_content = map_file_content
        self._all_vm = all_vm
        self._section_filter = section_filter
        self._type_filter = type_filter

    def get_sections(self, file_path: Path) -> AnalysisResult | None:
        """
        Analyzes the given file using bloaty and returns all identified `Section`. In case of any errors, `None` will be returned.
        The sections will only be added to the output, if they pass the given filters.
        If a map file is provided all sections that are removed by the linker will be removed from the output.

        :param file_path: the file to analyze.

        :return: on success, all identified `Section`. Otherwise, `None` will be returned.
        """
        sections = []
        total_vm_size = 0
        total_file_size = 0
        bloaty_output = self.get_bloaty_output(file_path)

        if bloaty_output:
            for line in bloaty_output.splitlines()[1:]:
                line_split = line.split(",")

                if len(line_split) == 3 and line_split[1].isdigit() and line_split[2].isdigit():
                    section_type = self.get_section_type(line_split[0])
                    section = Section(line_split[0], section_type, int(line_split[1]), int(line_split[2]))

                    if section.vm_size > 0 or self._all_vm:
                        if self.check_section_map_file(section) and self.check_section_filter(section) and self.check_section_type_filter(section):
                            sections.append(section)
                            total_vm_size = total_vm_size + section.vm_size
                            total_file_size = total_file_size + section.file_size
                else:
                    _LOGGER.error(f"bloaty output contains invalid line: {line}")
                    return None
            return AnalysisResult(file_path, sections, total_vm_size, total_file_size)
        else:
            return None

    def get_bloaty_output(self, file_path: Path) -> str | None:
        """
        Runs bloaty on the given file and collects its stdout if bloaty returns successfully. If it reports an error, `None` will be returned.
        The following args are passed to bloaty:
        - `-s vm`: Sort the output by VM size.
        - `-n 0`: Output all sections.
        - `--csv`: Output as CSV to stdout, which is easier to parse than the normal output.

        :param file_path: the file to analyze using bloaty.

        :return: on success, the bloaty stdout is returned. Otherwise, `None` will be returned.
        """
        res = subprocess.run([_BLOATY_CMD, "-s", "vm", "-n", "0", "--csv", f"{file_path.as_posix()}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if res.returncode == 0:
            return res.stdout.decode()
        else:
            _LOGGER.error(f"bloaty returned with: {res.returncode}. stdout: {res.stdout.decode()}. stderr: {res.stderr.decode()}")
            return None

    def get_section_type(self, section_name: str) -> SectionType:
        """Gets the type of the section based on its name. If this is not possible the type will be set to `unkown`."""
        for type in SectionType:
            if section_name.startswith(f".{type.name}"):
                return type
        return SectionType.unknown

    def check_section_map_file(self, section: Section) -> bool:
        """Check if the section is contained in the map file (and thus was not removed by the linker)."""
        return self._map_file_content is None or section.name in self._map_file_content

    def check_section_filter(self, section: Section) -> bool:
        """Check if the section name matches the user given regex. If no regex is given, always returns True."""
        return self._section_filter is None or re.compile(self._section_filter).match(section.name)

    def check_section_type_filter(self, section: Section) -> bool:
        """Check if the section type matches the user given type filter. If no filter is given, always returns True."""
        return len(self._type_filter) == 0 or section.section_type.name in self._type_filter


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Section size analyzer.")
    parser.add_argument(
        "--build-dir",
        help="Path to the build directory. If not given, the current working directory will be used instead."
    )
    parser.add_argument(
        "--map-file",
        help="Path to the map file. It is used to remove sections that got removed by the linker from the analysis results."
    )
    parser.add_argument(
        "--type-filter",
        help="Comma separated list of section types to filter for. For example '-t rodata,text' would only show rodata and text sections."
    )
    parser.add_argument(
        "--section-filter",
        help="Regex that will be applied to section names. Only the ones that match the regex will be considered."
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help="Write output to a CSV file instead of stdout."
    )
    parser.add_argument(
        "--all-vm",
        action="store_true",
        default=False,
        help="Also include sections with a VM size of 0."
    )

    args = parser.parse_args()

    build_dir = Path().cwd()
    map_file_content = None
    type_filter = []

    if not is_bloaty_installed():
        _LOGGER.error("bloaty is not installed. Please install it to use this tool.")
        exit(1)

    if args.build_dir:
        build_dir = Path(args.build_dir)

        if not build_dir.exists():
            _LOGGER.error(f"Given build directory: {build_dir} does not exist.")
            exit(1)

    if args.map_file:
        map_file_path = Path(args.map_file)

        if not map_file_path.exists():
            _LOGGER.error(f"Given map file: {map_file_path} does not exist.")
            exit(1)
        with open(args.map_file, "r") as f:
            map_file_content = f.read()

    if args.type_filter:
        type_filter = _remove_all_spaces(args.type_filter).split(",")

    if args.section_filter:
        try:
            re.compile(args.section_filter)
        except re.error:
            _LOGGER.error(f"Given regex: {args.section_filter} is not valid.")
            exit(1)

    console = Console()
    section_analyzer = SectionAnalyzer(map_file_content, args.all_vm, args.section_filter, type_filter)

    res = []
    overall_vm_size = 0
    overall_file_size = 0

    for file_path in build_dir.rglob("*.a"):
        analysis_result = section_analyzer.get_sections(file_path)

        if analysis_result:
            res.append(analysis_result)
            overall_vm_size = overall_vm_size + analysis_result.total_vm_size
            overall_file_size = overall_file_size + analysis_result.total_file_size

    res.sort(key=lambda x: x.total_vm_size, reverse=True)

    if args.csv:
        with open("output.csv", "w") as f:
            f.write("file_path,section,type,vm_size,file_size\n")

            for analysis_result in res:
                if analysis_result.total_vm_size > 0 or args.all_vm:
                    f.write(analysis_result.to_csv_lines())
    else:
        for analysis_result in res:
            if analysis_result.total_vm_size > 0 or args.all_vm:
                analysis_result.print(console, overall_vm_size, overall_file_size)
                console.print("")
