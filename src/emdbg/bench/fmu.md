# PX4 FMU test bench

The test bench consists of a PX4 FMU that is connected to a J-Link and a
USB-Serial adapter for the NSH.

The main entry point is the `emdbg.bench.fmu()` function, which orchestrates
the entire setup and yields an initialized bench object.

The FMU firmware must be compiled externally and is automatically uploaded when
the bench is set up. This ensures that you're always debugging the right
firmware, otherwise you will see very weird behavior, since GDB uses the ELF
file to locate statically allocated objects and understand types.

The FMU is then reset, held in that state, and then yielded from the function so
that you can configure the test and then start the firmware execution when
ready.

The FMU is configured for debugging by stopping all timers when the debugger
halts the CPU, therefore from the device's perspective, no time is missed
during debugging. If you want to know about the system load, you must start
it *before* querying it's state, otherwise there is nothing to compare the
current sample to.


## GDB Configuration File

This module also loads a `fmu.gdb` configuration file with many target-specific
GDB commands in addition to the PX4-specific commands defined by the Python
modules in `emdbg.debug.gdb`.

- `px4_log_start {filename}`: Starts logging of the GDB prompt to a file.
- `px4_log_stop`: Stops GDB logging.
- `px4_fbreak {func}`: Places a breakpoint on the return of a function.
- `px4_btfbreak {func}`: Same as `px4_fbreak` but prints a backtrace too.
- `px4_breaktrace{,10,100} {func}`: Sets a breakpoint on a function and calls
  `px4_backtrace` to produce a call chain that can be interpreted by
  `emdbg.analyze.callgraph`. The 10 and 100 suffixes indicate that the
  backtrace is only generated every 10 or 100 hits of the breakpoint.
- `px4_commands_backtrace{,10,100}`: Attach a backtrace to a previously defined
  breakpoint or watchpoint. `px4_breaktrace` uses this for breakpoints.
- `px4_calltrace_semaphore_boosts`: set breaktraces in the `sem_holder.c` file
  to log task (de-)boosts that can be interpreted by `emdbg.analyze.priority`.

To trace a watchpoint, you need to define it yourself and attach a backtrace:

```
(gdb) watch variable
(gdb) px4_commands_backtrace
```

## Scripting

This module gives you all functionality to automate a test. Remember that the
bench automatically uploads the firmware.

```py
with emdbg.bench.fmu(px4_dir, target, nsh_serial) as bench:
    # FMU is flashed with the firmware, reset and halted
    # Configure your test now
    bench.gdb.execute("px4_log_start log.txt")
    # Now execute from the reset handler onwards
    bench.gdb.continue_nowait()
    # wait for NSH prompt
    bench.nsh.wait_for_prompt()
    # Start the system load monitor
    bench.restart_system_load_monitor()
    bench.sleep(3)
    # Update system load monitor
    bench.restart_system_load_monitor()
    # Wait a little
    bench.sleep(5)
    # interrupt and automatically continue
    with bench.gdb.interrupt_continue():
        # Print the task list and cpu load
        print(emdbg.debug.px4.all_tasks_as_table(bench.gdb))
        # Dump the core
        bench.gdb.coredump()
    bench.sleep(10)
    # interrupt at the end
    bench.gdb.interrupt_and_wait()
    # Deconfigure GDB
    bench.gdb.execute("px4_log_stop")
```


## Command Line Interface

To quickly debug something interactively on the test bench, you can launch GDB
directly with the debug backend of your choice:

- `--jlink`: connect via J-Link debug probe.
- `--stlink`: connect via STLink debug probe.
- `--orbtrace`: connect via Orbtrace mini debug probe.
- `--coredump`: Use the CrashDebug backend with a coredump or PX4 hardfault log.

```sh
python3 -m emdbg.bench.fmu --px4-dir path/to/PX4-Autopilot \
    --target px4_fmu-v5x_default -ui tui --stlink

python3 -m emdbg.bench.fmu --px4-dir path/to/PX4-Autopilot \
    --target px4_fmu-v6x_default --coredump px4_hardfault.log
```

