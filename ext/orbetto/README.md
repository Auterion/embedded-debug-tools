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
- Heap malloc/free with address and size.
- DMA transfer start/stop with configuration.
- Semaphore init/wait/post with count.

Perfetto is a FTrace visualizer that works really well for this use case:

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto2.png)

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto3.png)

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto4.png)

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto5.png)

![](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto6.png)

[Here is an example trace of only the scheduler](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto.perf),
[here is one with the scheduler and workqueues](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto_wq.perf),
[another one with heap tracking](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto_heap.perf),
[one with DMA transfer profiling](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto.perfetto_trace.gz),
and [one with semaphore count tracing](https://gist.githubusercontent.com/niklaut/608160cd9917888b22750f5f773c7265/raw/orbetto_semaphores.perfetto_trace.gz), 
that you can download and drag into the [the Perfetto UI](https://ui.perfetto.dev)
to test it yourself.


## Installation

Please install the following dependencies:

```sh
# Ubuntu
sudo apt-get install -y libusb-1.0-0-dev libzmq3-dev meson libsdl2-dev libdwarf-dev libdw-dev libelf-dev libcapstone-dev python3-pip ninja-build protobuf-compiler
sudo pip3 install meson==1.2.0
# macOS
brew install libusb zmq sdl2 libelf dwarfutils protobuf meson ninja capstone
```

Then build the `build/orbetto` binary:

```sh
meson setup build
ninja -C build
```


## Instrumentation

You need to apply one patches to your PX4 source tree:

```sh
# cd PX4-Autopilot
python3 -m emdbg.patch nuttx_tracing_itm_v11 --apply -v
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

To capture the trace output, we can use the STLinkv3-MINIE or a JLink.

Launch GDB inside your PX4-Autopilot source code directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v5x --stlink
```

Reset your target and start the capture:

```
(gdb) px4_trace_swo_stm32f7
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
(gdb) px4_trace_swo_stm32h7
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
# FMUv5x runs at 216MHz
build/orbetto -T s -C 216000 -E -f path/to/trace.swo -e path/to/fmu.elf
# FMUv6x runs at 480MHz
build/orbetto -T s -C 480000 -E -f path/to/trace.swo -e path/to/fmu.elf
```

You should now have a `orbetto.perf` file that you can drag into
[the Perfetto UI](https://ui.perfetto.dev).
