# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import os, sys, time

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
        "--digilent",
        dest="io",
        help="The identifier of the serial number of the Digilent Device.")
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
        "--type",
        required=True,
        choices=["debugger", "runtime"],
        help="The method to use for detecting boosts.")
    parser.add_argument(
        "--sample",
        default=240,
        type=int,
        help="Sample time in seconds.")
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    boost_log = args.log
    if boost_log is None:
        boost_log = emdbg.utils.add_datetime(f"log_boost_{args.type}.txt")

    with emdbg.bench.skynode(args.px4_dir, args.target, args.nsh, args.io) as bench:
        if args.type == "runtime":
            bench.nsh.log_to_file(boost_log)
        else:
            bench.gdb.execute("px4_calltrace_semaphore_boosts")
            bench.gdb.execute(f"px4_log_start {boost_log}")
        bench.gdb.continue_nowait()

        # Start MAVSDK Stress tester
        try:
            sproc = subprocess.Popen("(cd ext/arm_disarm_stresstest/build && ./arm_disarm_stresstest udp://:14550)",
                                     start_new_session=True, cwd=rootdir, shell=True)
            def check_subprocess(_):
                if (rc := sproc.poll()) is not None and rc != 0:
                    raise Exception("Could not connect to Companion")
            # collect boost log now
            bench.sleep(args.sample, check_subprocess)
        finally:
            if sproc.poll() is None:
                os.killpg(os.getpgid(sproc.pid), signal.SIGINT)

        # halt the debugger and stop logging
        bench.gdb.interrupt_and_wait()
        if args.type == "runtime":
            bench.nsh.log_to_file(None)
        else:
            bench.gdb.execute("px4_log_stop")
        # Analyze the log
        summary = "\n" + emdbg.analyze.summarize_semaphore_boostlog(boost_log)
        summary += bench.gdb.execute("px4_tasks", to_string=True)
        with boost_log.open("at") as f:
            f.write(summary)
        print(summary)
        # Convert log to call graph
        if args.type == "debugger":
            emdbg.analyze.callgraph_from_backtrace(boost_log, emdbg.analyze.SemaphoreBacktrace,
                                                      output_graphviz=boost_log.with_suffix(".svg"))
