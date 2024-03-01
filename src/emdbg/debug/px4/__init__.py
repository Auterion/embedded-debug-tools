# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
# GDB Python Modules

This module includes many PX4-specific GDB Python plugins that provide additional
debug functionality for interactive debugging and automated scripting.

Since we want these modules to work inside and outside of GDB, we do not use
`import gdb` which is only available inside GDB, but instead provide `gdb`
as a function argument so that it can be replaced by
`emdbg.debug.remote.rpyc.Gdb`.

.. warning::
    You must only use the [GDB Python API][api] and the Python standard library
    in this folder so that they work both inside and outside of GDB.


[api]: https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html
"""



from .task import all_tasks, all_tasks_as_table, all_files_as_table, task_switch
from .semaphore import Semaphore
from .perf import PerfCounter, all_perf_counters_as_table
from .buffer import UartBuffer, ConsoleBuffer
from .device import all_registers, all_registers_as_table, all_gpios_as_table
from .device import vector_table, vector_table_as_table, Device, coredump
from .device import discover as discover_device
from .svd import PeripheralWatcher

from .system_load import restart_system_load_monitor
from .utils import gdb_backtrace as backtrace
from .data import pinout


_TARGET = None
_SVD_FILE = None
