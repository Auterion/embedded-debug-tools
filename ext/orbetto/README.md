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

Perfetto is a FTrace visualizer that works really well for this use case:

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/c4946a3bbb1db20e8c0b80138b656e2a32868db9/orbetto.png)

[Here is an example trace](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/c4946a3bbb1db20e8c0b80138b656e2a32868db9/orbetto.perf)
that you can download and drag into the [the Perfetto UI](https://ui.perfetto.dev)
to test it yourself.


## Installation

Please install the following dependencies:

```sh
# macOS
brew install protobuf libusb zeromq ncurses sdl2 meson ninja
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

> **Note**  
> The patches are currently only available for NuttX v10, however, we will add
> support for upstream v11 and v12 soon.


## Capture

To capture the trace output, we use the STLinkv3-MINIE probe with up to 24Mbps
SWO logging capability, configured and controlled via GDB.
However, the FMUv5x SWO can only be clocked ~20MHz to prevent data corruption.

Launch GDB inside your PX4-Autopilot source code directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v5x --openocd
```

> **Note**  
> Currently the trace command is hardcoded for the FMUv5x, however, we will add
> support for FMUv6x soon.

Reset your target and start the capture:

```
(gdb) monitor reset halt
(gdb) px4_trace_swo
(gdb) continue
```

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
build/orbetto -T s -C 216000 -E -f path/to/trace.swo
```

You should now have a `orbetto.perf` file that you can drag into
[the Perfetto UI](https://ui.perfetto.dev).
