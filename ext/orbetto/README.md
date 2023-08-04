# Orbetto: NuttX Instrumentation with Perfetto

We can instrument the NuttX scheduler with very low CPU overhead (<5%) by
streaming the ITM/DWT debug trace over the SWO pin and capturing it to a file.

The functionality currently instrumented with cycle accuracy:

- Task creation with PID and name.
- Task renaming after creation.
- Task stopping.
- Task suspend/resume with suspend state and resume priority.
- Task waking (waiting to run).
- IRQ entry/exit.
- Workqueue start/stop with name.

Perfetto is a FTrace visualizer that works really well for this use case:

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto2.png)

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto3.png)

[Here is an example trace with workqueues](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto_wq.perf)
and [another without workqueues](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto.perf)
that you can download and drag into the [the Perfetto UI](https://ui.perfetto.dev)
to test it yourself.


## Installation

Please install the following dependencies:

```sh
# macOS
brew install protobuf libusb zeromq ncurses sdl2 meson ninja libelf libdwarf
```

Then build the `build/orbetto` binary:

```sh
meson setup build
ninja -C build
```


## Instrumentation

You need to apply two patches to your PX4 source tree:

```sh
# cd PX4-Autopilot
python3 -m emdbg.patch itm_logging --apply -v
python3 -m emdbg.patch nuttx_tracing_itm --apply -v
```

Then recompile and upload your PX4 firmware to your FMU:

```sh
make px4_fmu-v5x
python3 -m emdbg.debug.openocd upload --source build/px4_fmu-v5x_default/px4_fmu-v5x_default.elf
```


## Capture

You can use an STLink or J-Link for enabling SWO output on the FMUv5x. However,
OpenOCD does not currently support SWO on STM32H7 very well, so you will have
to use a J-Link for tracing the FMUv6x.


### FMUv5x

To capture the trace output, we use the STLinkv3-MINIE probe with up to 24Mbps
SWO logging capability, configured and controlled via GDB.
However, the FMUv5x SWO can only be clocked ~20MHz to prevent data corruption.

Launch GDB inside your PX4-Autopilot source code directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v5x --openocd
```

Reset your target and start the capture:

```
(gdb) monitor reset halt
(gdb) px4_trace_swo_v5x_openocd
(gdb) continue
```


### FMUv6x

FMUv6x can currently only be traced with J-Link:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v6x --jlink
```

Reset your target and start the capture:

```
(gdb) monitor reset
(gdb) px4_trace_swo_v6x_jlink
(gdb) continue
```


### Finish

Perform the testing you need to do to trigger what you need to debug, then quit
GDB:

```
^C
(gdb) quit
```

You will now have a `trace.swo` file in your directory that should be several
MBs large.


## Visualization

To convert the `trace.swo` binary file to the Perfetto format, call the
`orbetto` program:

```sh
# cd embedded-debug-tools/ext/orbetto
build/orbetto -T s -C 216000 -E -f path/to/trace.swo -e path/to/fmu.elf
```

You should now have a `orbetto.perf` file that you can drag into
[the Perfetto UI](https://ui.perfetto.dev).
