# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from functools import cached_property
from . import utils
from .system_load import system_load
from .device import Device
from .base import Base
from dataclasses import dataclass
from collections import defaultdict
import rich.box
from rich.text import Text
from rich.table import Table

# The mapping from register name to position on the thread stack
_XCP_REGS_MAP: dict[str, int] = {
    "msp":     0,
    "basepri": 1,
    "r4":      2,
    "r5":      3,
    "r6":      4,
    "r7":      5,
    "r8":      6,
    "r9":      7,
    "r10":     8,
    "r11":     9,
    "s16":     11 + 0,
    "s17":     11 + 1,
    "s18":     11 + 2,
    "s19":     11 + 3,
    "s20":     11 + 4,
    "s21":     11 + 5,
    "s22":     11 + 6,
    "s23":     11 + 7,
    "s24":     11 + 8,
    "s25":     11 + 9,
    "s26":     11 + 10,
    "s27":     11 + 11,
    "s28":     11 + 12,
    "s29":     11 + 13,
    "s30":     11 + 14,
    "s31":     11 + 15,
    "r0":      27 + 0,
    "r1":      27 + 1,
    "r2":      27 + 2,
    "r3":      27 + 3,
    "r12":     27 + 4,
    "r14":     27 + 5,
    "r15":     27 + 6,
    "xpsr":    27 + 7,
    "s0":      27 + 8,
    "s1":      27 + 9,
    "s2":      27 + 10,
    "s3":      27 + 11,
    "s4":      27 + 12,
    "s5":      27 + 13,
    "s6":      27 + 14,
    "s7":      27 + 15,
    "s8":      27 + 16,
    "s9":      27 + 17,
    "s10":     27 + 18,
    "s11":     27 + 19,
    "s12":     27 + 20,
    "s13":     27 + 21,
    "s14":     27 + 22,
    "s15":     27 + 23,
    "fpscr":   27 + 24,
}

class Task(Base):
    """
    NuttX task
    """
    _STACK_COLOR = 0xdeadbeef
    _FILE_DESCRIPTORS_PER_BLOCK = 6 # TODO query from ELF

    @dataclass
    class Load:
        total: int
        """Total task runtime in µs"""
        interval: int
        """Interval task runtime in µs since last sample"""
        delta: int
        """Task runtime in µs within the interval"""

        @property
        def relative(self) -> float:
            """Relative runtime within the interval"""
            return self.delta / self.interval if self.interval else 0

    def __init__(self, gdb, tcb_ptr: "gdb.Value"):
        super().__init__(gdb)
        self._tcb = tcb_ptr
        self._system_load = system_load(self._gdb)
        self.pid = self._tcb["pid"]
        self.init_priority = int(self._tcb["init_priority"])
        self.stack_limit = int(self._tcb["adj_stack_size"])
        self.stack_ptr = self._tcb["stack_base_ptr"]
        self._is_running_switched = None

    @cached_property
    def name(self) -> str:
        """Name of the task"""
        try:
            return self._tcb["name"].string()
        except:
            return "?"

    @cached_property
    def sched_priority(self) -> int:
        """The scheduled priority of the task"""
        return int(self._tcb["sched_priority"])

    @cached_property
    def _statenames(self):
        return self._gdb.types.make_enum_dict(self._gdb.lookup_type("enum tstate_e"))

    @cached_property
    def state(self) -> str:
        """Task state name"""
        for name, value in self._statenames.items():
            if value == self._tcb["task_state"]:
                return name
        return "UNKNOWN"

    @cached_property
    def short_state(self) -> str:
        """The short name of the task state"""
        mapping = {
            "TASK_PENDING": "PEND", "TASK_READYTORUN": "READY", "TASK_RUNNING": "RUN",
            "WAIT_SEM": "w:sem", "WAIT_SIG": "w:sig"}
        return mapping.get(self.state.replace("TSTATE_", ""), "???")

    def _is_state_in(self, *states: list[str]) -> bool:
        states = {int(self._statenames[s]) for s in states}
        if int(self._tcb["task_state"]) in states:
            return True
        return False

    @cached_property
    def is_waiting(self) -> bool:
        """The task is waiting for a semaphore or signal"""
        if self._is_state_in("TSTATE_WAIT_SEM", "TSTATE_WAIT_SIG"):
            return True

    @cached_property
    def is_runnable(self) -> bool:
        """The task is pending, ready to run, or running"""
        return self._is_state_in("TSTATE_TASK_PENDING",
                                 "TSTATE_TASK_READYTORUN",
                                 "TSTATE_TASK_RUNNING")

    @cached_property
    def stack_used(self) -> int:
        """The amount of stack used by the thread in bytes"""
        if not self.stack_ptr: return 0
        stack_u32p = self.stack_ptr.cast(self._gdb.lookup_type("unsigned int").pointer())
        # Stack grows from top to bottom, we do a binary search for the
        # 0xdeadbeef value from the bottom upwards
        watermark = utils.binary_search_last(stack_u32p, self._STACK_COLOR, hi=self.stack_limit // 4) + 1
        # validate the binary search (does not seem necessary)
        # for ii in range(0, watermark):
        #     if stack_u32p[ii] != self._STACK_COLOR:
        #         print(f"{self.name}: Correcting stack size from {watermark * 4} to {ii * 4}!")
        #         return ii * 4
        return self.stack_limit - watermark * 4

    @cached_property
    def waiting_for(self) -> str:
        """
        What the task is waiting for. If its a semaphore, return an object,
        otherwise a string.
        """
        if self._is_state_in("TSTATE_WAIT_SEM"):
            from .semaphore import Semaphore
            sem = self._tcb['waitsem']
            ostr = f"{int(sem):#08x} "
            if descr := self.description_at(sem): ostr += f"<{descr}> "
            ostr += Semaphore(self._gdb, sem).to_string()
            return ostr
        if self._is_state_in("TSTATE_WAIT_SIG"):
            return "signal"
        return ""

    @cached_property
    def files(self) -> list["gdb.Value"]:
        """The list of inode pointers the task holds"""
        filelist = self._tcb["group"]["tg_filelist"]
        rows = filelist["fl_rows"]
        files = filelist["fl_files"]
        result = []
        for ri in range(rows):
            for ci in range(self._FILE_DESCRIPTORS_PER_BLOCK):
                file = files[ri][ci]
                if inode := file["f_inode"]:
                    result.append(file)
        return result

    @cached_property
    def location(self) -> "gdb.Block":
        """The block the task is currently executing"""
        if self.is_current_task:
            pc = self.read_register("pc")
        else:
            pc = self._tcb["xcp"]["regs"][32]
        block = self.block(pc)
        while block and not block.function:
            block = block.superblock
        return block.function if block else int(pc)

    def switch_to(self) -> bool:
        """Switch to this task by writing the register file"""
        if self.is_current_task:
            return False
        regs = {name: self._tcb["xcp"]["regs"][offset]
                for name, offset in _XCP_REGS_MAP.items()}
        self.write_registers(regs)
        self._is_running_switched = True
        return True

    def switch_from(self) -> dict[str, int] | None:
        """Switch to this task by writing the register file"""
        if not self.is_current_task:
            return None
        self._is_running_switched = False
        if self.short_state == "RUN":
            self._is_running_switched = None
        return self.registers

    @cached_property
    def is_current_task(self) -> bool:
        """If the task is currently running"""
        if self._is_running_switched is not None:
            return self._is_running_switched
        return self.short_state == "RUN"

    @cached_property
    def load(self) -> Load:
        """The task load based on the system load monitor"""
        if self._system_load is None: return self.Load(0, 0, 0)
        _, interval, sl = self._system_load.sample
        total, delta = sl.get(int(self._tcb), (0,0))
        return self.Load(total, interval, delta)

    def __repr__(self) -> str:
        return f"Task({self.name}, {self.pid})"

    def __str__(self) -> str:
        ostr = self.__repr__() + f": state={self.state}, "
        ostr += f"prio={self.sched_priority}({self.init_priority}), "
        ostr += f"stack={self.stack_used}/{self.stack_limit}"
        if waiting := self.waiting_for:
            ostr += f", waiting={waiting}"
        return ostr


def all_tasks(gdb) -> list[Task]:
    """Return a list of all tasks"""
    type_tcb_s = gdb.lookup_type("struct tcb_s").pointer()
    def _tasks(name):
        tcbs = []
        if (task_list := gdb.lookup_global_symbol(name)) is None:
            return []
        task_list = task_list.value()
        current_task = task_list["head"]
        if current_task:
            while True:
                tcbs.append(Task(gdb, current_task.cast(type_tcb_s)))
                if current_task == task_list["tail"]:
                    break
                next_task = current_task["flink"]
                # if next_task["blink"] == current_task:
                #   LOGGER.error(f"Task linkage is broken in {tasks}!")
                #   break
                current_task = next_task
        return tcbs

    tcbs  = _tasks("g_pendingtasks")
    tcbs += _tasks("g_readytorun")
    tcbs += _tasks("g_waitingforsemaphore")
    tcbs += _tasks("g_waitingforsignal")
    tcbs += _tasks("g_inactivetasks")
    return tcbs


_RESTORE_REGISTERS = None
def task_switch(gdb, pid: int) -> bool:
    """
    Switch to another task.
    On initial switch the current register file is saved and can be restored
    by passing a PID <0.

    :param pid: the PID of the task to switch to, or <0 to restore initial task.
    :return: Success of switching operation.
    """
    global _RESTORE_REGISTERS
    # Restore registers to original task
    if pid < 0:
        if _RESTORE_REGISTERS is not None:
            Base(gdb).write_registers(_RESTORE_REGISTERS)
        _RESTORE_REGISTERS = None
        return True

    # Otherwise find the new pointer
    tcbs = all_tasks(gdb)
    if (next_task := next((t for t in tcbs if int(t.pid) == pid), None)) is not None:
        # Find the currently executing task and save their registers
        if (current_task := next((t for t in tcbs if t.is_current_task), None)) is not None:
            regs = current_task.switch_from()
        else:
            regs = Base(gdb).registers
        # We only care about the first register set for restoration
        if next_task.switch_to():
            if _RESTORE_REGISTERS is None:
                _RESTORE_REGISTERS = regs
            print(f"Switched to task '{next_task.name}' ({pid}).")
            return True

        print("Task already loaded!")
        return False

    print(f"Unknown task PID '{pid}'!")
    return False


def all_tasks_as_table(gdb, sort_key: str = None, with_stack_usage: bool = True,
                       with_file_names: bool = True, with_waiting: bool = True) \
                                    -> tuple[Table, str] | tuple[None, None]:
    """
    Return a table of running tasks similar to the NSH top command.

    :param sort_key: optional lambda function to sort the table rows.
    :param with_stack_usage: compute and show the task stack usage.
    :param with_file_names: show what files the task has open.
    :param with_waiting: show what the task is waiting for.

    :return: The task table and additional output. If no tasks are found, return `None`.
    """
    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("struct tcb_s*", justify="right", no_wrap=True)
    table.add_column("pid", justify="right", no_wrap=True)
    table.add_column("Task Name")
    table.add_column("Location", no_wrap=True)
    table.add_column("CPU(ms)", justify="right")
    table.add_column("CPU(%)", justify="right")
    table.add_column("Stack\nUsage", justify="right")
    table.add_column("Avail\nStack", justify="right")
    table.add_column("Prio", justify="right")
    table.add_column("Base", justify="right")
    if with_file_names: table.add_column("Open File Names")
    else: table.add_column("FDs", justify="right")
    table.add_column("State")
    if with_waiting: table.add_column("Waiting For")

    tasks = all_tasks(gdb)
    if not tasks: return None, None
    interval_us = tasks[0].load.interval
    if not interval_us:
        start, *_ = tasks[0]._system_load.sample
        total_interval_us = (Device(gdb).uptime - start) or 1
    total_user_us, total_idle_us = 0, 0
    rows = []
    for task in tasks:
        # Remember the CPU loads for idle task and add it for the other tasks
        if task.pid == 0: total_idle_us = task.load.delta if interval_us else task.load.total
        else: total_user_us += task.load.delta if interval_us else task.load.total

        # Find the file names or just the number of file descriptors
        if with_file_names:
            file_names = [task.read_string(f["f_inode"]["i_name"]) for f in task.files]
            file_description = ", ".join(sorted(list(set(file_names))))
        else:
            file_description = len(task.files)

        # Add all the values per row
        relative = task.load.relative if interval_us else task.load.total / total_interval_us
        stack_overflow = with_stack_usage and task.stack_used >= task.stack_limit
        row = [hex(task._tcb), task.pid, task.name,
               hex(task.location) if isinstance(task.location, int) else task.location.name,
               task.load.total//1000, f"{(relative * 100):.1f}",
               Text.assemble((str(task.stack_used) if with_stack_usage else "", "bold red" if stack_overflow else "")),
               Text.assemble((str(task.stack_limit), "bold" if stack_overflow else "")),
               Text.assemble((str(task.sched_priority), "bold red" if task.sched_priority > task.init_priority else "")),
               task.init_priority, file_description, task.short_state]
        if with_waiting:
            row.append(task.waiting_for)
        rows.append(row)

    # Sort the rows by PID by default and format the table
    for row in sorted(rows, key=lambda l: l[1] if sort_key is None else sort_key):
        table.add_row(*[r if isinstance(r, Text) else str(r) for r in row],
                      style="bold blue" if row[11] == "RUN" else None)

    # Add the task information
    running = sum(1 for t in tasks if t.is_runnable)
    sleeping = sum(1 for t in tasks if t.is_waiting)
    output = f"Processes: {len(tasks)} total, {running} running, {sleeping} sleeping\n"

    # Add CPU utilization and guard against division by zero
    if not interval_us: interval_us = total_interval_us
    user = 100 * total_user_us / interval_us;
    idle = 100 * total_idle_us / interval_us;
    sched = 100 * (interval_us - total_idle_us - total_user_us) / interval_us;
    output += f"CPU usage: {user:.1f}% tasks, {sched:.1f}% sched, {idle:.1f}% idle\n"

    # Uptime finally
    output += f"Uptime: {Device(gdb).uptime/1e6:.2f}s total, {interval_us/1e6:.2f}s interval\n"
    return table, output


def all_files_as_table(gdb, sort_key: str = None) -> Table | None:
    """
    Return a table of open files owned by tasks.

    :param sort_key: optional lambda function to sort the table rows.

    :return: The file table or `None` if no tasks exist.
    """
    tasks = all_tasks(gdb)
    if not tasks: return None

    files = {}
    file_tasks = defaultdict(set)
    for task in tasks:
        # Find the file names or just the number of file descriptors
        for f in task.files:
            files[int(f["f_inode"])] = f["f_inode"]
            file_tasks[int(f["f_inode"])].add(task)
    # Format the rows
    rows = []
    for addr, inode in files.items():
        rows.append((hex(addr),
                     hex(inode["i_private"]) if inode["i_private"] else "",
                     task.read_string(inode["i_name"]),
                     ", ".join(sorted(t.name for t in file_tasks[addr]))))
    # sort and add rows
    table = Table(box=rich.box.MINIMAL_DOUBLE_HEAD)
    table.add_column("struct inode*", justify="right", no_wrap=True)
    table.add_column("i_private*", justify="right", no_wrap=True)
    table.add_column("Name")
    table.add_column("Tasks")
    for row in sorted(rows, key=lambda l: l[2] if sort_key is None else sort_key):
        table.add_row(*row)
    return table
