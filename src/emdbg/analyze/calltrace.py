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
            "--ex",
            required=True,
            action="append",
            help="The commands to execute.")
        values = {
            "FileSystem": emdbg.analyze.FileSystemBacktrace,
            "SPI": emdbg.analyze.SpiBacktrace,
            "I2C": emdbg.analyze.I2cBacktrace,
            "CAN": emdbg.analyze.CanBacktrace,
            "UART": emdbg.analyze.UartBacktrace,
            "Semaphore": emdbg.analyze.SemaphoreBacktrace,
            "Generic": emdbg.analyze.Backtrace,
        }
        parser.add_argument(
            "--type",
            choices=values.keys(),
            default="Generic",
            help="The backtrace class to use.")
        args = parser.parse_args()
        emdbg.logger.configure(args.verbosity)
        backend = args.remote
        if args.openocd: backend = "openocd"
        if args.jlink: backend = "jlink"

        print(f"Logging for: {', '.join(args.ex)}")

        calltrace = "".join(filter(lambda c: re.match(r"[\w\d]", c), '_'.join(args.ex)))
        calltrace = Path(f"{args.log_prefix}_{calltrace}.txt")
        with emdbg.bench.fmu(args.px4_dir, args.target, backend=backend, upload=False) as bench:
            for ex in args.ex:
                bench.gdb.execute(ex)
                if any(ex.startswith(b) for b in ["break ", "watch ", "awatch ", "rwatch "]):
                    bench.gdb.execute("px4_commands_backtrace")
            bench.gdb.execute(f"px4_log_start {calltrace}")
            bench.gdb.continue_nowait()

            bench.sleep(args.sample)

            # halt the debugger and stop logging
            bench.gdb.interrupt_and_wait()
            bench.gdb.execute("px4_log_stop")
            emdbg.analyze.callgraph_from_backtrace(calltrace, values.get(args.type),
                                                   output_graphviz=calltrace.with_suffix(".svg"))
