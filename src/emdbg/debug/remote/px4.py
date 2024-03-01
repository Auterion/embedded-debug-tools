# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import gdb, argparse, shlex, re, traceback, functools
from collections import defaultdict
from rich.console import Console
# The import is relative only to the emdbg/debug folder, so that we do not pull
# in any other dependencies
import px4

_CONSOLE = Console(force_terminal=True)

def report_exception(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        try: return f(*args, **kwargs)
        except: print(traceback.format_exc())
    return inner


# Wrap functionality into user commands
class PX4_Discover(gdb.Command):
    """
    Find out what device we are connected to.
    """
    def __init__(self):
        super().__init__("px4_discover", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        _CONSOLE.print(px4.discover_device(gdb))


class PX4_Tasks(gdb.Command):
    """
    Print a table of all NuttX tasks and their current state.
    """
    def __init__(self):
        super().__init__("px4_tasks", gdb.COMMAND_USER)
        self.parser = argparse.ArgumentParser(self.__doc__)
        self.parser.add_argument("-f", "--files", default=False, action="store_true",
                                 help="Print the names of the open files.")

    @report_exception
    def invoke(self, argument, from_tty):
        args = self.parser.parse_args(shlex.split(argument))
        table, output = px4.all_tasks_as_table(gdb, with_file_names=args.files)
        if table is not None:
            _CONSOLE.print(table)
            print(output)
        else:
            print("No tasks found!")


class PX4_Files(gdb.Command):
    """
    Print a table of all open files and who is holding them.
    """
    def __init__(self):
        super().__init__("px4_files", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        table = px4.all_files_as_table(gdb)
        if table is not None:
            _CONSOLE.print(table)
        else:
            print("No tasks found!")


class PX4_Dmesg(gdb.Command):
    """
    Print the dmesg buffer.
    """
    def __init__(self):
        super().__init__("px4_dmesg", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        gdb.execute("print g_console_buffer")


class PX4_Perf(gdb.Command):
    """
    Print the perf counters.
    """
    def __init__(self):
        super().__init__("px4_perf", gdb.COMMAND_USER)
        self.header = ["pointer", "name", "events", "elapsed", "average", "least", "most", "rms", "interval", "first", "last"]
        self.parser = argparse.ArgumentParser(self.__doc__)
        self.parser.add_argument("name", help="Regex filter for perf counter names.", nargs='?')
        self.parser.add_argument("-s", "--sort", help="Column name to sort the table by.",
                                 choices=self.header)

    @report_exception
    def invoke(self, argument, from_tty):
        args = self.parser.parse_args(shlex.split(argument))
        def _perf_filter(pc):
            if args.name is not None and not re.search(args.name, pc.name):
                return False
            return True
        attr = args.sort
        def _sort_key(pc):
            if attr == "pointer": value = int(pc._perf)
            else: value = getattr(pc, attr)
            return (-1 if value is None else value, pc.name)

        table = px4.all_perf_counters_as_table(gdb, _perf_filter,
                        None if args.sort is None else _sort_key)

        if table is not None:
            _CONSOLE.print(table)
        else:
            print("No perf counters found!")


class PX4_Registers(gdb.Command):
    """
    Print a table of all Cortex-M registers.
    Optional argument is number of columns.
    """
    def __init__(self):
        super().__init__("px4_registers", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        _CONSOLE.print(px4.all_registers_as_table(gdb, int(argument or 3)))


class PX4_Interrupts(gdb.Command):
    """
    Print a table of all registered NuttX interrupts.
    EPA = Enabled/Pending/Active, P = (Shifted) Priority
    Optional argument is number of columns.
    """
    def __init__(self):
        super().__init__("px4_interrupts", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        _CONSOLE.print(px4.vector_table_as_table(gdb, int(argument or 1)))


class PX4_Gpios(gdb.Command):
    """
    Print a table of all GPIOs, their configuration and their FMU specific names.
    You can sort the table with the `-s COLUMN` option and filter it by pin name

    """
    def __init__(self):
        super().__init__("px4_gpios", gdb.COMMAND_USER)
        self.header = ["pin", "config", "in", "out", "af", "name", "function"]
        self.parser = argparse.ArgumentParser(self.__doc__)
        self.parser.add_argument("-f", "--filter", help="Regex filter for FMU names.")
        self.parser.add_argument("-ff", "--function-filter", help="Regex filter for FMU functions.")
        self.parser.add_argument("-pf", "--pin-filter", help="Regex filter for GPIO pin names.")
        self.parser.add_argument("-s", "--sort", help="Column name to sort the table by.",
                                 choices=self.header)
        self.parser.add_argument("-c", "--columns", type=int, default=2,
                                 help="Number of columns to print.")

    @report_exception
    def invoke(self, argument, from_tty):
        args = self.parser.parse_args(shlex.split(argument))
        pinout = px4.pinout(gdb, "fmu")
        columns = args.columns
        if args.pin_filter or args.filter or args.function_filter:
            columns = 1
        def pin_filter(row):
            if args.pin_filter is not None and not re.search(args.pin_filter, row[0]):
                return False
            if len(row) > 5:
                if args.filter is not None and not re.search(args.filter, row[5]):
                    return False
                if args.function_filter is not None and not re.search(args.function_filter, row[6]):
                    return False
            return True
        sort_by = self.header.index(args.sort) if args.sort is not None else None
        _CONSOLE.print(px4.all_gpios_as_table(gdb, pinout, pin_filter, sort_by, columns))


class PX4_Backtrace(gdb.Command):
    """
    Print a backtrace of the current frame.
    This works like `backtrace`, except it doesn't fail internal GDB assertions.
    """
    def __init__(self):
        super().__init__("px4_backtrace", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        print(px4.backtrace(gdb))


class PX4_Switch_Task(gdb.Command):
    """
    Switch to a task PID to inspect the task.
    """
    def __init__(self):
        super().__init__("px4_switch_task", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        pid = int(argument, 0) if argument else -1
        px4.task_switch(gdb, pid)


class PX4_Relative_Breakpoint(gdb.Command):
    """
    Finds the absolute location of a relative line number offset and then sets
    a breakpoint on that location. Backslashes in the regex pattern are preserved.

    Location format: `file:function:+offset` or `file:function:regex`.
    """
    def __init__(self):
        super().__init__("px4_rbreak", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        location = px4.utils.gdb_relative_location(gdb, argument)
        gdb.execute(f"break {location}")


class PX4_Coredump(gdb.Command):
    """
    Dump the volatile memories and registers.
    Optional argument is the filename.
    """
    def __init__(self):
        super().__init__("px4_coredump", gdb.COMMAND_USER)
        self.parser = argparse.ArgumentParser(self.__doc__)
        self.parser.add_argument("--memory", action="append",
                                 help="Memory range in `start:size` format.")
        self.parser.add_argument("--flash", action="store_true", default=False,
                                 help="Also dump the non-volatile memory.")
        self.parser.add_argument("--file",
                                 help="Coredump filename, defaults to `coredump_{datetime}.txt`.")

    @report_exception
    def invoke(self, argument, from_tty):
        args = self.parser.parse_args(shlex.split(argument))
        memories = None
        if args.memory:
            memories = [[int(h, 0) for h in m.split(":")] for m in args.memory]
        px4.coredump(gdb, memories, args.flash, args.file)


class PX4_Watch_Peripheral(gdb.Command):
    """
    Visualize the differences in peripheral registers on every GDB stop event.
    """
    def __init__(self, filename):
        super().__init__("px4_pwatch", gdb.COMMAND_USER)
        self.parser = argparse.ArgumentParser(self.__doc__)
        self.parser.add_argument("name", nargs="*",
                                 help="One or more peripheral or peripheral register names: PER or PER.REG .")
        self.parser.add_argument("--add", "-a", action="store_true", default=False,
                                 help="Add these peripherals.")
        self.parser.add_argument("--remove", "-r", action="store_true", default=False,
                                 help="Remove these peripherals.")
        self.parser.add_argument("--reset", "-R", action="store_true", default=False,
                                 help="Reset watcher to peripheral reset values.")
        self.parser.add_argument("--quiet", "-q", action="store_true", default=False,
                                 help="Stop automatically reporting.")
        self.parser.add_argument("--loud", "-l", action="store_true", default=False,
                                 help="Automatically report on GDB stop event.")
        self.parser.add_argument("--all", "-x", action="store_true", default=False,
                                 help="Show all logged changes.")
        self.parser.add_argument("--watch-write", "-ww", action="store_true", default=False,
                                 help="Add a write watchpoint on registers.")
        self.parser.add_argument("--watch-read", "-wr", action="store_true", default=False,
                                 help="Add a read watchpoint on registers.")
        self.do_report = True
        self.last_report = {}
        self.all_report = {}
        self.watchpoints = {}
        self.svd = px4.PeripheralWatcher(gdb, filename)
        gdb.events.stop.connect(self.on_stop)

    @report_exception
    def invoke(self, argument, from_tty):
        args = self.parser.parse_args(shlex.split(argument))
        if args.add:
            for name in args.name:
                report = self.svd.watch(name)
                if args.loud: print(report)
                arange = self.svd.address(name).values()
                amin, amax = min(a[0] for a in arange), max(a[1] for a in arange)
                match (args.watch_read, args.watch_write):
                    case (False, False): command = None
                    case (True,  False): command = "rwatch"
                    case (False, True):  command = "watch"
                    case (True,  True):  command = "awatch"
                if command:
                    ceil2 = 1 << (amax - amin - 1).bit_length()
                    command = f"{command} *(uint8_t[{ceil2}]*){hex(amin)}"
                    print(command)
                    output = gdb.execute(command, to_string=True)
                    print(output)
                    if match := re.match(r"Hardware watchpoint (\d+):", output):
                        self.watchpoints[name] = int(match.group(1))
        elif args.remove:
            for name in args.name:
                self.svd.unwatch(name)
                if name in list(self.watchpoints.keys()):
                    gdb.execute(f"delete {self.watchpoints.pop(name)}")
            if not args.name:
                self.svd.unwatch()
                for name in list(self.watchpoints.keys()):
                    gdb.execute(f"delete {self.watchpoints.pop(name)}")
        elif args.reset:
            for name in args.name:
                self.svd.reset(name)
            if not args.name:
                self.svd.reset()
        elif args.quiet:
            self.do_report = False
        elif args.loud:
            self.do_report = True
        else:
            for name in (args.name or [None]):
                print(self.report(name, args.all))

    @report_exception
    def report(self, name=None, show_all=False):
        report_map = self.all_report if show_all else self.last_report
        output = []
        if name is not None:
            for register in sorted(self.svd._find(name), key=lambda r: r[1].address_offset):
                if report := report_map.get(register, ""):
                    output.append(report)
        else:
            peripherals = defaultdict(list)
            for register in report_map:
                peripherals[register[0]].append(register)
            for peripheral in sorted(peripherals, key=lambda p: p.base_address):
                if report := self.report(peripherals[peripheral], show_all):
                    output.append(f"Differences for {peripheral.name}:")
                    output.append(report)
        return "\n".join(output)

    @report_exception
    def on_stop(self, event):
        self.last_report = {}
        for reg in self.svd._watched:
            if report := self.svd.report(reg):
                self.last_report[reg] = report
                self.all_report[reg] = report
        if self.do_report:
            print(self.report())
        self.svd.update()


class PX4_Show_Peripheral(gdb.Command):
    """
    Show the value and descriptions of one peripherals and optional register.
    Note: This will read register with side-effects!
    """
    def __init__(self, filename):
        super().__init__("px4_pshow", gdb.COMMAND_USER)
        if filename is None:
            filename = px4.device.Device(gdb)._SVD_FILE
        gdb.execute(f"arm loadfile st {filename}")

    @report_exception
    def invoke(self, argument, from_tty):
        gdb.execute(f"arm inspect /hab st {argument}")


# Instantiate all user commands
PX4_Discover()
PX4_Tasks()
PX4_Files()
PX4_Dmesg()
PX4_Perf()
PX4_Registers()
PX4_Interrupts()
PX4_Gpios()
PX4_Switch_Task()
PX4_Relative_Breakpoint()
PX4_Backtrace()
PX4_Coredump()
PX4_Watch_Peripheral(px4._SVD_FILE)
PX4_Show_Peripheral(px4._SVD_FILE)


# Functions for use in GDB scripts
class PX4_Relative_Location(gdb.Function):
    """
    Finds the absolute location of a relative line number offset.
    Note that backslashes in the regex must be double escaped!!!
    """
    def __init__(self):
        super().__init__("px4_rloc")

    @report_exception
    def invoke(self, location):
        return px4.utils.gdb_relative_location(gdb, location.string())


class PX4_IsValid(gdb.Function):
    """Is a variable valid? = not <optimized out> and not <unavailable>."""
    def __init__(self):
        super().__init__("px4_valid")

    def invoke(self, var):
        if var.is_optimized_out:
            return 0
        descr = str(var)
        if descr in ["<optimized out>", "<unavailable>"]:
            return 0
        else:
            return 1


# Instantiate all user functions
PX4_Relative_Location()
PX4_IsValid()


# Internal development helpers
class PX4_Reload(gdb.Command):
    """
    Reloads the px4 module internally. This can have unwanted side-effects!
    """
    def __init__(self):
        super().__init__("px4_reload", gdb.COMMAND_USER)

    @report_exception
    def invoke(self, argument, from_tty):
        px4.utils._Singleton._instances = {}
        import importlib
        # importlib.reload(px4)
        importlib.reload(px4.base)
        importlib.reload(px4.device)
        importlib.reload(px4.data)
        importlib.reload(px4.semaphore)
        importlib.reload(px4.buffer)
        importlib.reload(px4.perf)
        importlib.reload(px4.svd)
        importlib.reload(px4.system_load)
        importlib.reload(px4.task)
        importlib.reload(px4.utils)
        gdb.execute(f"source /Users/niklaut/dev/Better-Tooling/embedded-debug-tools/src/emdbg/debug/remote/px4.py")

# Instantiate all internal commands
PX4_Reload()

# Pretty Printers
def _px4_pretty_printer(val):
    stype = str(val.type)
    if stype == "sem_t" or stype == "struct sem_s":
        return px4.Semaphore(gdb, val)
    if stype == "struct uart_buffer_s":
        return px4.UartBuffer(gdb, val)
    if stype == "ConsoleBuffer" or stype == "class ConsoleBuffer":
        return px4.ConsoleBuffer(gdb, val)
    return None
gdb.pretty_printers.append(_px4_pretty_printer)
