# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
You can generate semaphore boosts logs either at runtime using the
`emdbg.patch.set.semaphore_boostlog` patch, or using the
`px4_calltrace_semaphore_boosts` command of the `emdbg.bench.skynode` module
at debug time.


## Command Line Interface

You can summarize boost logs:

```sh
python3 -m emdbg.analyze.priority log_semaphore_boosts.txt
```

You can also generate a callgraph with boost operations:

```sh
python3 -m emdbg.analyze.callgraph log_semaphore_boosts.txt --svg --type Semaphore
```
"""

from __future__ import annotations
import re
from pathlib import Path
import statistics
import itertools
from collections import defaultdict
from ..debug.px4.utils import format_table
from .utils import read_gdb_log

class _BoostOperation:
    PATTERN = re.compile(r"L(\d+) +(\d+)us> +(0x[0-9a-f]+|<opti-out>): +(.*?) +(\d+) +([\\/_]+) +(\d+) *(.*)")

    def __init__(self, description):
        self.is_valid = False
        if match := self.PATTERN.search(description):
            self.line = int(match.group(1))
            self.uptime = int(match.group(2))
            try:
                self.semaphore = int(match.group(3), 16)
            except:
                self.semaphore = None
            self.task = match.group(4)
            self.prio_from = int(match.group(5))
            self.operation = match.group(6)
            self.prio_to = int(match.group(7))
            self.reason = None if not match.group(8) else match.group(8)
            self.is_valid = True

    def __repr__(self) -> str:
        return f"{self.task} {self.prio_from} {self.operation} {self.prio_to}"


def summarize_semaphore_boostlog(logfile: Path) -> str:
    """
    Analyze a boost log and create a statistical summary and return it.

    :param logfile: The boostlog file to analyze
    :return: A formatted string containing the analysis.
    """
    output = []

    ops = []
    for line in read_gdb_log(logfile).splitlines():
        op = _BoostOperation(line)
        if op.is_valid:
            ops.append(op)
        # else:
        #     print(line)
    if not ops: return "No task boosts found!"
    ops.sort(key=lambda o: o.uptime)


    uptime = ops[-1].uptime
    sample_time = max(o.uptime for o in ops) - min(o.uptime for o in ops)
    output.append(f"Uptime: {uptime/1e6:.1f}s = {uptime/6e7:.1f}min")
    output.append(f"Sample time: {sample_time/1e6:.1f}s = {sample_time/6e7:.1f}min")

    # Print summary statistics
    prios = []
    def _mean(values):
        return int((statistics.fmean(values) if len(values) else 0) / 1e3)
    def _stdev(values):
        if len(values) >= 2: return int(statistics.stdev(values) / 1e3)
        return values[0] if len(values) else 0

    diffs = [n.uptime - p.uptime for p,n in itertools.pairwise(ops)]
    prios.append(["All", len(ops), _mean(diffs), _stdev(diffs)])

    boost_up = [op for op in ops if op.operation == "_/"]
    diffs_up = [n.uptime - p.uptime for p,n in itertools.pairwise(boost_up)]
    prios.append(["Up", len(boost_up), _mean(diffs_up), _stdev(diffs_up)])

    boost_down = [op for op in ops if op.operation == "\\_"]
    diffs_down = [n.uptime - p.uptime for p,n in itertools.pairwise(boost_down)]
    prios.append(["Down", len(boost_down), _mean(diffs_down), _stdev(diffs_down)])

    boost_255 = [op for op in ops if op.operation == "_/" and op.prio_to == 255]
    diffs_255 = [n.uptime - p.uptime for p,n in itertools.pairwise(boost_255)]
    prios.append(["255", len(boost_255), _mean(diffs_255), _stdev(diffs_255)])

    fmtstr = "{:%d}  {:>%d} ~{:>%d}ms ±{:>%d}ms"
    header = ["KIND", "#BOOSTS", "MEAN", "STDEV"]
    output.append("")
    output.append(format_table(fmtstr, header, prios))

    # Print summary statistics per task
    fmtstr = "{:%d}  {:>%d} {:>%d}%%  [{:>%d}, {:>%d}]   {:%d}   {:>%d}  {:%d}"
    header = ["TASK", "#BOOSTS", "PCT", "MIN", "MAX", "REASONS", "#MAX", "REASONS FOR MAX"]
    tasks = defaultdict(list)
    for op in ops:
        tasks[op.task].append(op)
    task_prios = [[
            task,
            boosts := sum(1 for o in ops if o if o.operation == "_/"),
            f"{boosts * 100 / len(boost_up):.1f}",
            min(o.prio_from for o in ops),
            max_prio := max(o.prio_to for o in ops),
            ", ".join(sorted({o.reason for o in ops if o.reason is not None})),
            sum(1 for o in ops if o if o.operation == "_/" and o.prio_to == max_prio),
            ", ".join(sorted({o.reason for o in ops if o.reason is not None and o.prio_to == max_prio}))
        ]
        for task, ops in tasks.items()]
    task_prios.sort(key=lambda t: (t[4], t[3], t[0], t[1]))
    output.append("")
    output.append(format_table(fmtstr, header, task_prios))

    semtasks = defaultdict(list)
    semtasksr = defaultdict(list)
    for op in ops:
        if op.semaphore is not None:
            semtasks[op.semaphore].append(op.task)
            if op.reason: semtasksr[op.semaphore].append(op.reason)
    semtasks = [[hex(s), len(ts), ", ".join(sorted(set(ts))), ", ".join(sorted(set(semtasksr.get(s, []))))] for s, ts in semtasks.items()]
    semtasks.sort(key=lambda s: -s[1])
    fmtstr = "{:%d}  {:>%d}  {:%d}  {:%d}"
    header = ["SEMAPHORE", "#BOOSTS", "BOOSTS THESE TASKS", "BECAUSE OF THESE TASKS"]
    output.append("")
    output.append(format_table(fmtstr, header, semtasks))

    return "\n".join(output)


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Priority Ceiling Analyzer")
    parser.add_argument(
        "file",
        type=Path,
        help="The GDB log containing the semaphore boost trace.")
    args = parser.parse_args()

    print(summarize_semaphore_boostlog(args.file))




