# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import os, sys, time

import re
import emdbg
import argparse
import logging
import subprocess
from pathlib import Path
import signal
LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Debug setup')
    parser.add_argument(
        "--px4-dir",
        default=".",
        type=Path,
        help="The PX4 root directory you are working on.")
    parser.add_argument(
        "--target",
        default="px4_fmu-v5x",
        help="The target you want to debug.")
    parser.add_argument(
        "--nsh",
        help="The identifier of the serial port connected to NSH.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level.")
    parser.add_argument(
        "--log",
        type=Path,
        help="Log file name.")
    parser.add_argument(
        "--sample",
        default=60,
        type=int,
        help="Sample time in seconds.")
    parser.add_argument(
        "--semaphore",
        required=True,
        help="The semaphore to call trace.")
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    try:
        semaphores = [int(args.semaphore, 16)]
    except:
        loglines = Path(args.semaphore).read_text().splitlines()
        PATTERN = re.compile(r"(0x[0-9a-f]+?)  +?\d+?  +?\w+")
        semaphores = [PATTERN.match(line) for line in loglines]
        semaphores = [int(m.group(1), 16) for m in semaphores if m is not None]

    print("Logging for: " + ", ".join(hex(s) for s in semaphores))

    for semaphore in semaphores:
        boost_log = args.log.with_suffix('') if args.log else "semaphore_access"
        boost_log = Path(f"{boost_log}_{hex(semaphore)}.txt")
        if args.log is None:
            boost_log = emdbg.utils.add_datetime(boost_log)
        with emdbg.bench.skynode(args.px4_dir, args.target, args.nsh) as bench:
            bench.gdb.execute(f"px4_calltrace_semaphore {semaphore}")
            bench.gdb.execute(f"px4_log_start {boost_log}")
            bench.gdb.continue_nowait()

            bench.sleep(args.sample)

            # halt the debugger and stop logging
            bench.gdb.interrupt_and_wait()
            bench.gdb.execute("px4_log_stop")
            emdbg.analyze.callgraph_from_backtrace(boost_log, emdbg.analyze.SemaphoreBacktrace,
                                                      output_graphviz=boost_log.with_suffix(".svg"))
        time.sleep(2)
