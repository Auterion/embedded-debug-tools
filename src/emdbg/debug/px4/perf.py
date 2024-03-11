# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from .base import Base
from .utils import format_units
from typing import Callable, Any
import rich.box, rich.markup
from rich.table import Table
from functools import cached_property
import math


class PerfCounter(Base):
    """
    Pretty Printing Perf Counters
    """

    def __init__(self, gdb, perf_ptr: "gdb.Value"):
        super().__init__(gdb)
        self._perf = perf_ptr.cast(gdb.lookup_type("struct perf_ctr_count").pointer())
        if self.type == "PC_ELAPSED":
            self._perf = self._perf.cast(gdb.lookup_type("struct perf_ctr_elapsed").pointer())
        elif self.type == "PC_INTERVAL":
            self._perf = self._perf.cast(gdb.lookup_type("struct perf_ctr_interval").pointer())
        # print(self._perf, self.short_type, self.events, self.name)

    @cached_property
    def name(self) -> str:
        """Name of the counter"""
        try:
            return self._perf["name"].string()
        except:
            return "?"

    @cached_property
    def events(self) -> int:
        """How many events were counted"""
        return int(self._perf["event_count"])

    @cached_property
    def _types(self):
        return self._gdb.types.make_enum_dict(self._gdb.lookup_type("enum perf_counter_type"))

    @cached_property
    def type(self) -> str:
        """Counter type name"""
        for name, value in self._types.items():
            if value == self._perf["type"]:
                return name
        return "UNKNOWN"

    @cached_property
    def short_type(self) -> str:
        """The short name of the type"""
        return self.type.replace("PC_", "").capitalize()

    @cached_property
    def elapsed(self) -> int | None:
        """
        How much time has elapsed in microseconds.
        Only applies to Elapsed counters.
        """
        if self.type == "PC_ELAPSED":
            return int(self._perf["time_total"])
        return None

    @cached_property
    def first(self) -> int | None:
        """
        The first time in microseconds.
        Only applies to Interval counters.
        """
        if self.type == "PC_INTERVAL":
            return int(self._perf["time_first"])
        return None

    @cached_property
    def last(self) -> int | None:
        """
        The last time in microseconds.
        Only applies to Interval counters.
        """
        if self.type == "PC_INTERVAL":
            return int(self._perf["time_last"])
        return None

    @cached_property
    def interval(self) -> int | None:
        """
        The interval time in microseconds.
        Only applies to Interval counters.
        """
        if self.type == "PC_INTERVAL":
            return self.last - self.first
        return None

    @cached_property
    def average(self) -> int | None:
        """
        The average time in microseconds.
        Only applies to Elapsed and Interval counters.
        """
        if self.type == "PC_ELAPSED":
            return self.elapsed / self.events if self.events else 0
        elif self.type == "PC_INTERVAL":
            return (self.last - self.first) / self.events if self.events else 0
        return None

    @cached_property
    def least(self) -> int | None:
        """
        The least time in microseconds.
        Only applies to Elapsed and Interval counters.
        """
        if self.type in ["PC_ELAPSED", "PC_INTERVAL"]:
            return int(self._perf["time_least"])
        return None

    @cached_property
    def most(self) -> int | None:
        """
        The most time in microseconds.
        Only applies to Elapsed and Interval counters.
        """
        if self.type in ["PC_ELAPSED", "PC_INTERVAL"]:
            return int(self._perf["time_most"])
        return None

    @cached_property
    def rms(self) -> int | None:
        """
        The root mean square in microseconds.
        Only applies to Elapsed and Interval counters.
        """
        if self.type in ["PC_ELAPSED", "PC_INTERVAL"]:
            return 1e6 * math.sqrt(float(self._perf["M2"]) / (self.events - 1)) if self.events > 1 else 0
        return None


_PREVIOUS_COUNTERS = {}
def all_perf_counters_as_table(gdb, filter_: Callable[[PerfCounter], bool] = None,
                               sort_key: Callable[[PerfCounter], Any] = None) -> Table | None:
    """
    Pretty print all perf counters as a table. Counters that did not change
    since the last call are dimmed.

    :param filter_: A function to filter the perf counters.
    :param sort_key: A function to sort the perf counters by key.
    :returns: A rich table with all perf counters or `None` if no counters found.
    """
    if (queue := gdb.lookup_static_symbol("perf_counters")) is None:
        return None
    queue = queue.value()
    item, tail = queue["head"], queue["tail"]
    counters = []
    loop_count = 0
    while item and item != tail:
        pc = PerfCounter(gdb, item)
        counters.append(pc)
        item = item["flink"]
        loop_count += 1
        if loop_count > 1000: break
    # Filter may result in no matches
    if not counters:
        return None

    global _PREVIOUS_COUNTERS
    changed = {c for c in counters
               if (events := _PREVIOUS_COUNTERS.get(int(c._perf))) is not None
               and events != c.events}
    _PREVIOUS_COUNTERS |= {int(c._perf): c.events for c in counters}

    # Filter out the counters
    if filter_ is not None:
        counters = [c for c in counters if filter_(c)]
        if not counters:
            return None

    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("perf_ctr_count*", justify="right", no_wrap=True)
    table.add_column("Name")
    table.add_column("Events", justify="right")
    table.add_column("Elapsed", justify="right")
    table.add_column("Average", justify="right")
    table.add_column("Least", justify="right")
    table.add_column("Most", justify="right")
    table.add_column("RMS", justify="right")
    table.add_column("Interval", justify="right")
    table.add_column("First", justify="right")
    table.add_column("Last", justify="right")

    # Sort the rows by name by default and format the table
    for counter in sorted(counters, key=sort_key or (lambda p: p.name)):
        table.add_row(hex(counter._perf), rich.markup.escape(counter.name), str(counter.events),
                      format_units(counter.elapsed, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.average, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.least, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.most, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.rms, "t:µs", fmt=".3f", if_zero="-"),
                      format_units(counter.interval, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.first, "t:µs", fmt=".1f", if_zero="-"),
                      format_units(counter.last, "t:µs", fmt=".1f", if_zero="-"),
                      style="dim" if changed and counter not in changed else None)
    return table


