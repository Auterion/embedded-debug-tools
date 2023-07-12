# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: calltrace.md
"""

if __name__ == "__main__":
    import re
    import emdbg
    import argparse
    from pathlib import Path


    if __name__ == "__main__":
        parser = argparse.ArgumentParser(description="Generate call graphs of a function or memory location")
        parser.add_argument(
            "--px4-dir",
            default=".",
            type=Path,
            help="The PX4 root directory you are working on.")
        parser.add_argument(
            "--target",
            default="px4_fmu-v5x",
            help="The target you want to debug.")
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--jlink",
            default=False,
            action="store_true",
            help="Use a J-Link debug probe")
        group.add_argument(
            "--openocd",
            default=False,
            action="store_true",
            help="Use an OpenOCD debug probe")
        group.add_argument(
            "--remote",
            help="Connect to a remote GDB server: 'IP:PORT'")
        parser.add_argument(
            "-v",
            dest="verbosity",
            action="count",
            default=0,
            help="Verbosity level.")
        parser.add_argument(
            "--log-prefix",
            type=Path,
            default="calltrace",
            help="Log file name.")
        parser.add_argument(
            "--sample",
            default=60,
            type=int,
            help="Sample time in seconds.")
        parser.add_argument(
            "--trace",
            required=True,
            action="append",
            help="The break- or watchpoints to trace.")
        args = parser.parse_args()
        emdbg.logger.configure(args.verbosity)
        backend = args.remote
        if args.openocd: backend = "openocd"
        if args.jlink: backend = "jlink"

        print(f"Logging for: {', '.join(args.trace)}")

        calltrace = "".join(filter(lambda c: re.match(r"[\w\d]", c), '_'.join(args.trace)))
        calltrace = Path(f"{args.log_prefix}_{calltrace}.txt")
        with emdbg.bench.fmu(args.px4_dir, args.target, backend=backend, upload=False) as bench:
            for trace in args.trace:
                bench.gdb.execute(trace)
                bench.gdb.execute("px4_commands_backtrace")
            bench.gdb.execute(f"px4_log_start {calltrace}")
            bench.gdb.continue_nowait()

            bench.sleep(args.sample)

            # halt the debugger and stop logging
            bench.gdb.interrupt_and_wait()
            bench.gdb.execute("px4_log_stop")
            emdbg.analyze.callgraph_from_backtrace(calltrace, emdbg.analyze.Backtrace,
                                                   output_graphviz=calltrace.with_suffix(".svg"))
