# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
PX4 generates a log file if it encounters a hardfault.
This tool converts this to a coredump that can be loaded with CrashDebug.
To interpret the hardfault location and reason, use the GDB plugins.

.. note::
   The hardfault log only contains a copy of the stack and registers. The
   converter fills unknown memory with the `0xfeedc0de` value, which may then
   display wrong or incomplete results in some of the GDB plugins. Keep this in
   mind when converting a hardfault to a coredump.


## Command Line Interface

To convert the hardfault log:

```sh
# convert to hardfault_coredump.txt
python3 -m emdbg.analyze.hardfault hardfault.log
# or with an explicit name
python3 -m emdbg.analyze.hardfault hardfault.log -o custom_name.txt
```
"""

from __future__ import annotations
import re
from pathlib import Path
import statistics
import itertools
from collections import defaultdict

# FIXME: hardcoded for FMUv6x memory layout (also works for FMUv5x)
_ADDR_RANGES = [
    (0x2000_0000, 0x80000),
    (0x2400_0000, 0x80000),
    (0x3000_0000, 0x48000),
    (0x3800_0000, 0x10000),
    (0x3880_0000, 0x01000),
    (0xE004_2000, 4), # DEVID F7
    (0x5C00_1000, 4), # DEVID H7
    (0xE000_E000, 0xFFF), # SCS
]

_UNKNOWN_MEM = 0xfeedc0de

_UNKNOWN_REGS = [
    "r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "sp", "lr", "pc",
    "xpsr", "msp", "psp", "primask", "basepri", "faultmask", "control", "fpscr",
    "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11", "s12", "s13", "s14", "s15", "s16",
    "s17", "s18", "s19", "s20", "s21", "s22", "s23", "s24", "s25", "s26", "s27", "s28", "s29", "s30", "s31",
    "d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10", "d11", "d12", "d13", "d14", "d15",
]

def convert(log: str) -> str:
    """
    Convert a hardfault log to

    :param log: The content of a hardfault log file.
    :return: A formatted string containing the coredump.
    """
    lines = log.splitlines()

    known_mems = {}
    regs = {r: _UNKNOWN_MEM for r in _UNKNOWN_REGS}
    fault_regs = {}
    for line in lines:
        if len(reg_matches := re.findall(r" (r\d+|sp|lr|pc|xpsr|basepri|control|primask):\[?(0x[0-9a-f]+)]?", line)):
            for reg, val in reg_matches:
                regs[reg] = int(val, 16)
                if reg == "sp":
                    regs["msp"] = regs["sp"]
                    regs["psp"] = regs["sp"]

        if len(fault_matches := re.findall(r" (c|h|d|mm|b|a|ab)fsr:\[?(0x[0-9a-f]+)]?", line)):
            for reg, val in fault_matches:
                fault_regs[reg] = int(val, 16)

        m_base = re.match(r"^(0x[0-9a-f]+)\s(0x[0-9a-f]+).*$", line)
        m_correlated = re.match(r"^(0x[0-9a-f]+)\s0x[0-9a-f]+ -> \[(0x[0-9a-f]+)].*$", line)

        m = m_correlated or m_base

        if m:
            addr = int(m.group(1), 16)
            val = int(m.group(2), 16)
            known_mems[addr] = val

    # FIXME: hardcoded for FMUv5x (STM32F765)
    known_mems[0xE004_2000] = 0x10030451
    # FIXME: hardcoded for FMUv6x (STM32H753)
    known_mems[0x5C00_1000] = 0x10030450

    # CPUID
    known_mems[0xE000_ED00] = 0x411fc270
    # dump all the fault registers back into memory
    known_mems[0xE000_ED28] = fault_regs.get("c", 0)
    known_mems[0xE000_ED2C] = fault_regs.get("h", 0)
    known_mems[0xE000_ED30] = fault_regs.get("d", 0)
    known_mems[0xE000_ED34] = fault_regs.get("mm", 0)
    known_mems[0xE000_ED38] = fault_regs.get("b", 0)
    known_mems[0xE000_ED3C] = fault_regs.get("a", 0)
    known_mems[0xE000_EFA8] = fault_regs.get("ab", 0)

    output = []
    for mem_start, mem_size in _ADDR_RANGES:
        for addr in range(mem_start, mem_start + mem_size, 16):
            fmt = "{:#8x}:\t{:#8x}\t{:#8x}\t{:#8x}\t{:#8x}"
            fmt = fmt.format(addr, known_mems.get(addr, _UNKNOWN_MEM),
                                   known_mems.get(addr + 4, _UNKNOWN_MEM),
                                   known_mems.get(addr + 8, _UNKNOWN_MEM),
                                   known_mems.get(addr + 12, _UNKNOWN_MEM))
            output.append(fmt)

    for reg, val in regs.items():
        output.append(f"{reg:15} {val:#20x} {val:20}")

    return "\n".join(output)



# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hardfault log converter")
    parser.add_argument(
        "log",
        type=Path,
        help="The hardfault log.")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="The GDB log containing the semaphore boost trace.")
    args = parser.parse_args()

    if (outfile := args.output) is None:
        outfile = args.log.with_suffix("_coredump.txt")

    outfile.write_text(convert(args.log.read_text()))




