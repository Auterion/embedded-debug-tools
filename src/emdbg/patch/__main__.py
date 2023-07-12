# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import argparse
import emdbg.patch
from inspect import getmembers, isfunction
from pathlib import Path

# Find all patches automatically
map_patches = {n:f for n,f in getmembers(emdbg.patch, isfunction) if not n.startswith("_")}

parser = argparse.ArgumentParser(
    description="Applies")
parser.add_argument(
    "patch",
    choices=map_patches.keys(),
    help="Which patches to apply.")
parser.add_argument(
    "--px4-dir",
    default=".",
    type=Path,
    help="The PX4 root directory you are working on.")
parser.add_argument(
    "-v",
    dest="verbosity",
    action="count",
    help="Verbosity level.")

group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--apply", action="store_true")
group.add_argument("--restore", action="store_true")

args = parser.parse_args()
emdbg.logger.configure(args.verbosity)

patchset = map_patches[args.patch](args.px4_dir)

if args.apply:
    patchset.do()
if args.restore:
    patchset.undo()
