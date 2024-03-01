# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import re
import math

from datetime import datetime
from itertools import zip_longest
from pathlib import Path


# -----------------------------------------------------------------------------
def gdb_getfield(value: "gdb.Value", name: str, default=None):
    """Find the field of a struct/class by name"""
    for f in value.type.fields():
        if name == f.name:
            return value[name]
    return default


def gdb_iter(obj):
    """yields the values in an array or value with a range"""
    if hasattr(obj, "value"):
        obj = obj.value()
    if hasattr(obj.type, "range"):
        for ii in range(*obj.type.range()):
            yield obj[ii]
    else:
        return []

def gdb_len(obj) -> int:
    """Computes the length of a gdb object"""
    if hasattr(obj.type, "range"):
        start, stop = obj.type.range()
        return stop - start
    else:
        return 1

def gdb_backtrace(gdb) -> str:
    """
    Unfortunately the built-in gdb command `backtrace` often crashes when
    trying to resolve function arguments whose memory is inaccessible due to
    optimizations or whose type is too complex.
    Therefore this is a simpler implementation in Python to avoid GDB crashing.

    ```
    (gdb) px4_backtrace
    #0  0x0800b3be in sched_unlock() at platforms/nuttx/NuttX/nuttx/sched/sched/sched_unlock.c:272
    #1  0x0800b59e in nxsem_post() at platforms/nuttx/NuttX/nuttx/sched/semaphore/sem_post.c:175
    #2  0x0800b5b6 in sem_post() at platforms/nuttx/NuttX/nuttx/sched/semaphore/sem_post.c:220
    #3  0x08171570 in px4::WorkQueue::SignalWorkerThread() at platforms/common/px4_work_queue/WorkQueue.cpp:151
    #4  0x08171570 in px4::WorkQueue::Add(px4::WorkItem*) at platforms/common/px4_work_queue/WorkQueue.cpp:143
    #5  0x0816f8dc in px4::WorkItem::ScheduleNow() at platforms/common/include/px4_platform_common/px4_work_queue/WorkItem.hpp:69
    #6  0x0816f8dc in uORB::SubscriptionCallbackWorkItem::call() at platforms/common/uORB/SubscriptionCallback.hpp:169
    #7  0x0816f8dc in uORB::DeviceNode::write(file*, char const*, unsigned int) at platforms/common/uORB/uORBDeviceNode.cpp:221
    #8  0x0816faca in uORB::DeviceNode::publish(orb_metadata const*, void*, void const*) at platforms/common/uORB/uORBDeviceNode.cpp:295
    #9  0x081700bc in uORB::Manager::orb_publish(orb_metadata const*, void*, void const*) at platforms/common/uORB/uORBManager.cpp:409
    #10 0x0816e6d8 in orb_publish(orb_metadata const*, orb_advert_t, void const*) at platforms/common/uORB/uORBManager.hpp:193
    #11 0x08160912 in uORB::PublicationMulti<sensor_gyro_fifo_s, (unsigned char)4>::publish(sensor_gyro_fifo_s const&) at platforms/common/uORB/PublicationMulti.hpp:92
    #12 0x08160912 in PX4Gyroscope::updateFIFO(sensor_gyro_fifo_s&) at src/lib/drivers/gyroscope/PX4Gyroscope.cpp:149
    #13 0x08040e74 in Bosch::BMI088::Gyroscope::BMI088_Gyroscope::FIFORead(unsigned long long const&, unsigned char) at src/drivers/imu/bosch/bmi088/BMI088_Gyroscope.cpp:447
    #14 0x08041102 in Bosch::BMI088::Gyroscope::BMI088_Gyroscope::RunImpl() at src/drivers/imu/bosch/bmi088/BMI088_Gyroscope.cpp:224
    #15 0x0803fb7a in I2CSPIDriver<BMI088>::Run() at platforms/common/include/px4_platform_common/i2c_spi_buses.h:343
    #16 0x0817164c in px4::WorkQueue::Run() at platforms/common/px4_work_queue/WorkQueue.cpp:187
    #17 0x08171798 in px4::WorkQueueRunner(void*) at platforms/common/px4_work_queue/WorkQueueManager.cpp:236
    #18 0x08014ccc in pthread_startup() at platforms/nuttx/NuttX/nuttx/libs/libc/pthread/pthread_create.c:59
    ```

    :return: the selected frame's backtrace without resolving function argument
    """
    frame = gdb.selected_frame()
    index = 0
    output = []
    while(frame and frame.is_valid()):
        pc = frame.pc()
        if pc > 0xffff_ff00:
            output.append(f"#{index: <2} <signal handler called>")
        else:
            line = "??"
            file = "??"
            if sal := frame.find_sal():
                line = sal.line
                if sal.symtab:
                    file = sal.symtab.fullname()
            if func := frame.function():
                func = func.print_name
                if not func.endswith(")"): func += "()"
            else:
                func = "??"
            output.append(f"#{index: <2} 0x{pc:08x} in {func} at {file}:{line}")
        frame = frame.older()
        index += 1
    return "\n".join(output)

def gdb_relative_location(gdb, location) -> str:
    """
    GDB can only place breakpoint on specific line number inside a file.
    However, if the file changes the line numbers can shift around, which makes
    this method brittle. Therefore this function finds the function inside
    the file and applies a offset or searches for a pattern inside that function
    to determine the correct line number.

    :param location:
        Location `function:+offset` or `function:regex`. In case the function
        uses static linkage you may also need to provide a unique part of the
        filename path to arbitrate multiple identically named static functions
        `file:function:+offset` or `file:function:regex`.

    :return: absolute location string `file:line_number`
    """
    parts = location.split(":")
    file_name = None
    if len(parts) == 3:
        file_name, function_name, line_pattern = parts
    elif len(parts) == 2:
        function_name, line_pattern = parts
    else:
        raise ValueError(f"Unknown location format '{location}'!")()

    function = gdb.lookup_global_symbol(function_name, gdb.SYMBOL_VAR_DOMAIN)
    if function is None:
        # Multiple static symbols may exists, we use the filename to arbitrate
        if functions := gdb.lookup_static_symbols(function_name, gdb.SYMBOL_VAR_DOMAIN):
            file_functions = [(f.symtab.fullname(), f) for f in functions]
            # Arbitrate using file name hint
            if file_name is not None:
                file_functions = [f for f in file_functions if file_name in f[0]]
            if len(file_functions) == 1:
                function = file_functions[0][1]
            else:
                raise ValueError("Multiple functions found:\n - " + "\n - ".join(functions))
    if function is None:
        raise ValueError(f"Cannot find function name '{function_name}'")
    assert function.is_function

    # Find source file and line numbers: how to use file_name?
    file = function.symtab.fullname()
    line_numbers = function.symtab.linetable().source_lines()
    lmin, lmax = min(line_numbers), max(line_numbers)

    if line_pattern.startswith("+"):
        # line offset relative to function
        line = int(line_pattern[1:]) + function.line
    else:
        # regex line pattern, read source file and find the line
        lines = Path(file).read_text().splitlines()
        lines = list(enumerate(lines[lmin:lmax]))
        for ii, line in lines:
            if re.search(line_pattern, line):
                line = lmin + ii
                break
        else:
            lines = "\n  ".join(f"{lmin+l[0]:>4}: {l[1]}" for l in lines)
            raise ValueError(f"Cannot find source line for '{line_pattern}'!\n"
                f"Function '{function_name}' stretches over lines {lmin}-{lmax}.\n")
                # f"Available source lines are:\n  {lines}")

    return f"{file}:{line}"


# -----------------------------------------------------------------------------
def _binary_search(array, value, lo: int, hi: int, direction: int):
    middle = (lo + hi) // 2
    if hi - lo <= 1: return middle

    nslice = [(lo, middle), (middle, hi)]
    pick_lower_half = array[middle] == value
    if direction > 0: pick_lower_half = 1 - pick_lower_half

    lo, hi = nslice[pick_lower_half]
    return _binary_search(array, value, lo, hi, direction)

def binary_search_last(array, value, lo: int = None, hi: int = None):
    """Binary search the last occurrance of value in an array"""
    if lo is None: lo = 0
    if hi is None: hi = len(array)
    return _binary_search(array, value, lo, hi, direction=-1)

def binary_search_first(array, value, lo: int = None, hi: int = None):
    """Binary search the first occurrance of value in an array"""
    if lo is None: lo = 0
    if hi is None: hi = len(array)
    return _binary_search(array, value, lo, hi, direction=1)


# -----------------------------------------------------------------------------
def chunks(iterable, chunk_size: int, fill=None):
    """Convert a iterable into a list of chunks and fill the rest with a value"""
    args = [iter(iterable)] * chunk_size
    return zip_longest(*args, fillvalue=fill)


def add_datetime(filename: str|Path):
    """
    Appends a filename with the current date and time:
    `Year_Month_Day_Hour_Minute_Second`

    Example: `path/name.txt` -> `path/name_2023_04_14_15_03_24.txt`
    """
    filename = Path(filename)
    return filename.with_stem(f"{filename.stem}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}")


def format_units(value: int | float | None, prefixes: dict[str, int] | str,
                 unit: str = None, fmt: str = None, if_zero: str = None) -> str:
    """
    Format a value with the largest prefix.

    The value is divided by the list of prefixes until it is smaller than the
    next largest prefix. Trailing zeros are replaced by spaces and padding is
    applied to align the prefixes and units. If the value is zero, the
    `if_zero` string is returned if defined.

    Predefined prefixes can be passed as a `group:input-prefix`:
    - `t`: time prefixes from nanoseconds to days.
    - `si`: SI prefixes from nano to Tera.

    .. note:: The micro prefix is µ, not u.

    Example:

    ```py
    format_units(123456, "t:µs", fmt=".1f")    # "123.5ms"
    format_units(0, "t:s", if_zero="-")        # "-"
    format_units(1234, "si:", "Hz", fmt=".2f") # "1.23kHz"
    format_units(1001, "si:", "Hz", fmt=".2f") # "1   kHz"
    format_units(2345, {"k": 1e3, "M": 1e3}, "Si", fmt=".1f") # "2.3MSi"
    ```

    :param value: An integer or floating point value. If None, an empty string is returned.
    :param prefixes:
        A dictionary of prefix string to ratio of the next largest prefix. The
        dictionary must be sorted from smallest to largest prefix. The prefix of
        the input value must be the first entry.
    :param unit: A unit string to be appended to the formatted value.
    :param fmt: A format specifier to be applied when formatting the value.
    :param if_zero: A string to be returned when the value is zero.
    """
    if value is None: return ""
    if if_zero is not None and value == 0: return if_zero

    # Find the correct prefix from a list of predefined common prefixes
    _found = False
    if prefixes.startswith("t:"):
        time_units = {"ns": 1e3, "µs": 1e3, "ms": 1e3, "s": 60, "m": 60, "h": 24, "d": 365.25/12}
        prefixes = prefixes.split(":")[1]
        prefixes = {k:v for k, v in time_units.items() if _found or (_found := (k == prefixes))}
    elif prefixes.startswith("si:"):
        prefixes = prefixes.split(":")[1]
        prefixes = {k:1e3 for k in ["n", "µ", "m", "", "k", "M", "G", "T"]
                    if _found or (_found := (k == prefixes))}

    # Divide the value until it is smaller than the next largest prefix
    for prefix, factor in prefixes.items():
        if value < factor: break
        value /= factor

    # Format the value
    value = f"{value:{fmt or ''}}"
    value_stripped = value.rstrip("0").rstrip(".")
    if if_zero is not None and value_stripped == "0": return if_zero
    # pad the value to the right to align it
    padding = max(len(p) for p in prefixes.keys()) - len(prefix)
    padding += len(value) - len(value_stripped)
    return f"{value_stripped}{padding * ' '}{prefix}{unit or ''}"


# -----------------------------------------------------------------------------
def format_table(fmtstr: str, header: list[str], rows: list[list[str]], columns: int = 1) -> str:
    """
    DEPRECATED: Use `rich.table.Table` instead!

    Formats a list of rows into a table of multiple meta-columns based on the format string.
    Example for formatting an array of registers into a table with three meta-columns:

    ```py
    fmtstr = "{:%d}  {:>%d}  {:>%d}"
    header = ["NAME", "HEX VALUE", "INT VALUE"]
    rows = [[reg, hex(value), value] for reg, value in registers.items()]
    table = utils.format_table(fmtstr, header, rows, 3)
    ```

    :param fmtstr: A string describing the spacing between columns and their
                   alignment. Must have exactly as many entries as the header a
                   rows. Example: two columns, aligned right and left with a
                   brace formatter: `"{:>%d} ({:%d})"` The `%d` is replaced by
                   the max column width by this function.
    :param header: A list of names for the header row. If you specify more than
                   one column, the header will be duplicated.
    :param rows: a list of lists of entries in the table. Each entry will be
                 converted to `str` to count the maximal length of each column.
    :param columns: If a table is very long, the header can be duplicated to the
                    right side of the table to fill more screen space.
    """
    # duplicate and join the format string for each column
    split_horizontal = columns > 0
    columns = abs(columns)
    fmtstr = "      :      ".join([fmtstr] * columns)
    fmtcnt = fmtstr.count("%d")
    column_width = [0] * fmtcnt

    # Interleave the rows for the later chunking
    fill = [""] * (fmtcnt // columns)
    if split_horizontal:
        rows = [val for tup in zip(*chunks(rows, math.ceil(len(rows) / columns), fill)) for val in tup]
    # prepend the duplicated header before the rows
    if header is not None:
        rows = [header] * columns + rows
    # Group the individual rows into multiple columns per row
    rows = [sum(rs, []) for rs in chunks(rows, columns, fill)]

    # collect each line and compute the column width
    lines = []
    for row in rows:
        if len(row) != fmtcnt:
            raise ValueError("Each row have the same number of entries as the format string")
        line = [str(l) for l in row]
        lines.append(line)
        column_width = [max(w, len(l)) for w, l in zip(column_width, line)]

    # Format the format string with the column width first
    fmtstr = fmtstr % tuple(column_width)
    # Now format the actual lines with the formatted format string
    return "\n".join(fmtstr.format(*line).rstrip() for line in lines) + "\n"


# -----------------------------------------------------------------------------
class _Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
