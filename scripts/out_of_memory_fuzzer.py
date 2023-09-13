# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import os, sys, time, re

import emdbg
import argparse
import logging
from pathlib import Path
LOGGER = logging.getLogger(__name__)


def fuzz(out_dir: Path, px4_dir: Path, target: str, nsh: str, start: int):
    triggers = {}
    if out_dir:
        out_dir.mkdir(exist_ok=True, parents=True)

    with emdbg.bench.fmu(px4_dir, target, nsh, backend="jlink", upload=False) as bench:
        bench.gdb.execute("px4_reset")
        bench.gdb.execute("b arm_hardfault")
        bench.gdb.execute("b up_assert")
        bench.gdb.execute("b emdbg_malloc_is_null")

        for ii in range(start, 10000):
            bench.gdb.execute("px4_reset")
            print(f"Failing malloc call #{ii}...")
            bench.gdb.execute(f"set emdbg_malloc_count_null = {ii}")
            bench.gdb.read()
            bench.nsh.clear()

            # Second breakpoint will be emdbg_malloc_is_null()
            if bench.gdb.continue_wait(timeout=30):
                malloc_backtrace = bench.gdb.execute(f"px4_backtrace", to_string=True) + "\n"
                bench.gdb.execute("set disassemble-next-line off")
            else:
                print("malloc breakpoint timed out!")
                exit(1)

            # Third breakpoint will be hardfault or assertion
            fail_backtrace = ""
            if bench.gdb.continue_wait(timeout=3):
                fail_backtrace += bench.gdb.execute("px4_backtrace", to_string=True) + "\n"
                fail_backtrace += bench.gdb.execute("frame 2", to_string=True) + "\n"
                bench.gdb.execute("set disassemble-next-line off")
                fail_backtrace += bench.gdb.execute("px4_registers", to_string=True) + "\n"
                fail_backtrace += bench.gdb.execute("arm scb /h", to_string=True) + "\n"
                print(fail_backtrace)
                print(malloc_backtrace)

            # unless the NULL malloc is
            lines = bench.nsh.read_lines()
            print("\n".join(l for l in lines if l.startswith("ERROR ")))

            if out_dir:
                logfile = out_dir / f"log_{ii}.txt"
                logfile.write_text(fail_backtrace + malloc_backtrace + "\n".join(lines))

            bench.gdb.interrupt_and_wait()


def analyze(log_dir: Path):
    logs = list(log_dir.glob("log_*.txt"))
    log_count = len(logs)
    print(f"Looking at {log_count} logs...")

    logs_hardfault = {}
    logs_error = {}
    logs_silent = {}
    for log in logs:
        text = log.read_text()
        if "<signal handler called>" in text:
            assert "emdbg_malloc_is_null" in text
            logs_hardfault[log] = text
            continue
        if "ERROR" in text.replace("ERROR [SPI_I2C] icm42688p: no instance", ""):
            logs_error[log] = text
            continue
        # if "ERROR" in text:
        #     print(log)
        logs_silent[log] = text

    print(f"Logs (hardfault): {len(logs_hardfault)}")
    # print("  - " + "\n  - ".join(map(str, logs_hardfault.keys())))
    print(f"Logs (error): {len(logs_error)}")
    # print("  - " + "\n  - ".join(map(str, logs_error.keys())))
    print(f"Logs (silent): {len(logs_silent)}")
    # print("  - " + "\n  - ".join(map(str, logs_silent.keys())))

    bts_hardfault = [t.split("ABFSR - M7")[1] for t in logs_hardfault.values()]
    emdbg.analyze.callgraph_from_backtrace(bts_hardfault, emdbg.analyze.Backtrace,
                             output_graphviz="malloc_hardfaults.svg")

    bts_hardfault = [re.split(r" in \?\? at \?\?|Breakpoint", t)[0] for t in logs_hardfault.values()]
    emdbg.analyze.callgraph_from_backtrace(bts_hardfault, emdbg.analyze.Backtrace,
                             output_graphviz="malloc_hardfaults_trace.svg")

    bts_error = [re.split(r"#\d+ 0x00000000 in ??|Breakpoint", t)[0] for t in logs_error.values()]
    emdbg.analyze.callgraph_from_backtrace(bts_error, emdbg.analyze.Backtrace,
                             output_graphviz="malloc_error.svg")

    bts_silent = [re.split(r"#\d+ 0x00000000 in ??|Breakpoint", t)[0] for t in logs_silent.values()]
    emdbg.analyze.callgraph_from_backtrace(bts_silent, emdbg.analyze.Backtrace,
                             output_graphviz="malloc_silent.svg")



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fuzz out-of-memory conditions on PX4")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory to place log files in.")
    subparsers = parser.add_subparsers(title="Task", dest="task")

    fuzz_parser = subparsers.add_parser("fuzz", help="Make malloc fail deterministically.")
    fuzz_parser.add_argument(
        "--px4-dir",
        default=".",
        type=Path,
        help="The PX4 root directory you are working on.")
    fuzz_parser.add_argument(
        "--target",
        help="The target you want to debug.")
    fuzz_parser.add_argument(
        "--nsh",
        help="The identifier of the serial port connected to NSH.")
    fuzz_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Malloc fail number to start at.")

    subparsers.add_parser("analyze", help="Generate callgraphs from the traces.")

    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    if args.task == "fuzz":
        fuzz(args.out_dir, args.px4_dir, args.target, args.nsh, args.start)
    elif args.task == "analyze":
        analyze(args.out_dir)

