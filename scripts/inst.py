# Copyright (c) 2024, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import emdbg
import argparse
import logging

LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instrumentation helper")
    parser.add_argument(
        "--px4-dir",
        help="The PX4 root directory you are working on.",
        required=True,
    )
    parser.add_argument(
        "--target",
        help="The target you want to debug.",
        required=True
    )
    parser.add_argument(
        "--nsh",
        help="The identifier of the serial port connected to NSH.",
        required=True
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=0,
        help="The channel of the relay.")
    parser.add_argument(
        "--inverted",
        action="store_true",
        default=False,
        help="Channel is inverted.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        default=0,
        help="Verbosity level."
    )

args = parser.parse_args()
emdbg.logger.configure(args.verbosity)

power = emdbg.power.yocto_relay(args.channel, args.inverted)

with emdbg.bench.fmu(args.px4_dir, args.target, args.nsh, backend="jlink", power=power, upload=True) as bench:
    bench.gdb.continue_nowait()

    bench.nsh.wait_for_prompt(10)
    print(bench.nsh.command("ver all"))

exit(0)