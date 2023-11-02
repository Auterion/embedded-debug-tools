# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from functools import cached_property
from dataclasses import dataclass
from . import utils
from .base import Base


class Semaphore(Base):
    """
    Accessor for a NuttX semaphore
    """

    @dataclass
    class Holder:
        task: "emdbg.debug.px4.task.Task"
        """The task this holder belongs to"""
        count: int
        """How many times the task is holding this semaphore"""

    def __init__(self, gdb, sem_ptr: "gdb.Value"):
        super().__init__(gdb)
        self._sem = sem_ptr
        self.count: int = self._sem["semcount"]
        """Semaphore count, positive if available, 0 if taken, negative if tasks are waiting"""

    @cached_property
    def flags(self) -> int:
        """:return: The flags field of the semaphore"""
        return utils.gdb_getfield(self._sem, "flags", 0b1)

    @cached_property
    def holders(self) -> list[Holder]:
        """:return: a list of semaphore holders"""
        from .task import Task

        #if CONFIG_SEM_PREALLOCHOLDERS == 0
        if holder := utils.gdb_getfield(self._sem, "holder"):
            return [self.Holder(Task(self._gdb, holder[0]["htcb"]), int(holder[0]["counts"]))]

        #if CONFIG_SEM_PREALLOCHOLDERS > 0
        holders = []
        holder = self._sem["hhead"]
        while(holder):
            holders.append(self.Holder(Task(self._gdb, holder["htcb"]), int(holder["counts"])))
            holder = holder["flink"]
        return holders

    @property
    def has_priority_inheritance(self) -> bool:
        """:return: `True` if the semaphore supports priority inheritance"""
        return not (self.flags & 0b1)

    def to_string(self) -> str:
        sc = self.count
        state = "taken" if sc <= 0 else "available"
        ostr = f"{state} ({sc}{'i' if self.has_priority_inheritance else ''})"
        if hstr := [f"{h.count}x {h.task.name}" for h in self.holders]:
            ostr += f" holders: {', '.join(hstr)}"
        return ostr
