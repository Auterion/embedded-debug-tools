# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from functools import cached_property
from . import utils
from .base import Base
from .device import Device
import logging
LOGGER = logging.getLogger(__name__)


class SystemLoad(Base):
    """
    PX4 system load monitor using the `cpuload.cpp` module inside PX4.
    Do not use this class directly, instead access the cpu load information via
    the `emdbg.debug.px4.task.all_tasks_as_table()` function.
    """
    def __init__(self, gdb):
        super().__init__(gdb)
        self._device = Device(gdb)
        self._system_load = self.lookup_global_symbol_ptr("system_load")
        self._monitor = self.lookup_static_symbol_ptr("cpuload_monitor_all_count")
        self._psl = None
        self.restart()

    def _load(self):
        sl = self._system_load.dereference()
        tasks = {"hrt": self._device.uptime, "start": int(sl["start_time"]), "tasks": {}}
        for task in utils.gdb_iter(sl["tasks"]):
            if not task["valid"]: continue
            tcb = int(task["tcb"])
            total = int(task["total_runtime"])
            tasks["tasks"][tcb] = total
        return tasks

    def restart(self):
        """
        Enables the cpuload monitor in PX4 and loads the first reference value.
        """
        if self._system_load is None: return
        if self._monitor.dereference()["_value"] == 0:
            self._gdb.execute("set cpuload_monitor_all_count = 1")
            self._gdb.execute(f"set system_load.start_time = {self._device.uptime}")
            for ii in range(1, self._system_load["tasks"].type.range()[1]):
                self._gdb.execute(f"set system_load.tasks[{ii}].total_runtime = 0")
                self._gdb.execute(f"set system_load.tasks[{ii}].curr_start_time = 0")
        self._psl = self._load()


    def stop(self):
        """Disables the cpuload monitor"""
        if self._monitor is None: return
        self._gdb.execute("set cpuload_monitor_all_count = 0")

    @cached_property
    def sample(self) -> tuple[int, int, dict[int, tuple[int, int]]]:
        """
        Samples the cpuload monitor and computes the difference to the last
        sample.
        :return: a tuple of (start time since enabled [µs], interval from last
                 sample [µs], tasks dict[tcb [ptr] -> (total runtime [µs], difference
                 from last sample [µs])]).
        """
        if self._system_load is None or not self._system_load["initialized"]:
            return (0, 0, {})

        sl = self._load()
        # compute the delta running times
        sample = {}
        for tcb, total in sl["tasks"].items():
            ptotal = self._psl["tasks"].get(tcb, total)
            sample[tcb] = (total, total - ptotal)
        interval = self._device.uptime - self._psl["hrt"]
        # remember the new system load as previous load
        self._psl = sl
        return (sl["start"], interval, sample)


_SYSTEM_LOAD = None
def system_load(gdb):
    """
    :return: The SystemLoad singleton object.
    """
    global _SYSTEM_LOAD
    if _SYSTEM_LOAD is None:
        _SYSTEM_LOAD = SystemLoad(gdb)
    return _SYSTEM_LOAD


def restart_system_load_monitor(gdb):
    """
    Starts the system load monitor if not started, else resets the sample
    interval to right now.
    """
    system_load(gdb).sample
    system_load(gdb).restart()
