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
    from .utils import read_gdb_log
    from ..bench.fmu import _arguments

    values = {
        "FileSystem": emdbg.analyze.FileSystemBacktrace,
        "SPI": emdbg.analyze.SpiBacktrace,
        "I2C": emdbg.analyze.I2cBacktrace,
        "CAN": emdbg.analyze.CanBacktrace,
        "UART": emdbg.analyze.UartBacktrace,
        "Semaphore": emdbg.analyze.SemaphoreBacktrace,
        "Generic": emdbg.analyze.Backtrace,
    }
    def _modifier(parser):
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
            "--type",
            choices=values.keys(),
            default="Generic",
            help="The backtrace class to use.")

    args, backend = _arguments("Generate call graphs of a function or memory location", _modifier)
    print(f"Logging for: {', '.join(args.commands)}")

    calltrace = "".join(filter(lambda c: re.match(r"[\w\d]", c), '_'.join(args.commands)))
    calltrace = Path(f"{args.log_prefix}_{calltrace}.txt")
    with emdbg.bench.fmu(args.px4_dir, args.target, backend=backend, upload=False) as bench:
        for ex in args.commands:
            bench.gdb.execute(ex)
            if any(ex.startswith(b) for b in ["break ", "watch ", "awatch ", "rwatch "]):
                bench.gdb.execute("px4_commands_backtrace")
        bench.gdb.execute(f"px4_log_start {calltrace}")
        bench.gdb.continue_nowait()

        bench.sleep(args.sample)

        # halt the debugger and stop logging
        bench.gdb.interrupt_and_wait()
        bench.gdb.execute("px4_log_stop")

        backtraces = re.split(r"(?:Breakpoint|Hardware .*?watchpoint) \d", read_gdb_log(calltrace)[20:])
        emdbg.analyze.callgraph_from_backtrace(backtraces, values.get(args.type),
                                               output_graphviz=calltrace.with_suffix(".svg"))
