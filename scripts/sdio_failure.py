# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import os, sys, time

import emdbg
import argparse
import logging
LOGGER = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Debug setup')
    parser.add_argument(
        "--px4-dir",
        required=True,
        help="The PX4 root directory you are working on.")
    parser.add_argument(
        "--target",
        required=True,
        help="The target you want to debug.")
    parser.add_argument(
        "--nsh",
        help="The identifier of the serial port connected to NSH.")
    parser.add_argument(
        "--io",
        help="The identifier of the serial number of the Digilent Device.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level.")
    parser.add_argument(
        "--coredump",
        help="Coredump name.")
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)


    with emdbg.bench.skynode(args.px4_dir, args.target, args.nsh, args.io,
                                with_rpyc=True) as bench:
        bench.gdb.continue_nowait()

        bench.nsh.wait_for_prompt(10)
        bench.nsh.command("commander arm -f")

        bench.nsh.wait_for(r"\[logger\] Opened full log file")
        bench.sleep(2)

        bench.disturb_sdcard_cmd_line()
        bench.restart_system_load_monitor()
        bench.sleep(1)

        bench.gdb.interrupt_and_wait()
        LOGGER.info("\n" + emdbg.debug.px4.all_tasks_as_table(bench.gdb))
        idle_task = next(t for t in emdbg.debug.px4.all_tasks(bench.gdb) if t.pid == 0)
        if idle_task.load.relative < 0.1:
            LOGGER.error("Idle task is starved, dumping core for analysis!")
            bench.coredump(args.coredump)
            exit(1)

