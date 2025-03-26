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
- Program counter sampling with function name lookup.

Perfetto is a FTrace visualizer that works really well for this use case:

![](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto2.png)

![](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto3.png)

![](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto4.png)

![](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto5.png)

![](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto6.png)

Example trace files that you can download and drag into the
[the Perfetto UI](https://ui.perfetto.dev) to test it yourself:

- [Scheduler and Workqueues](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto_wq.perfetto_trace.gz).
- [Allocations on Heap](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto_heap.perfetto_trace.gz).
- [DMA transfer profiling](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto_dma.perfetto_trace.gz).
- [Semaphore count tracing](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto_semaphores.perfetto_trace.gz).
- [Program counter sampling](https://github.com/niklaut/orbetto-support-files/raw/main/orbetto_pc.perfetto_trace.gz).


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
(gdb) px4_trace_swo_stm32f7 <TER_REG> <SWO_FREQ[Hz]>
(gdb) continue
```

- Values for `<TER_REG>` are as described in [TER_REG](#ter_reg).
- The value of `<SWO_FREQ>` should be ≤20MHz to get reliable tracing.


### FMUv6x

FMUv6x can currently only be traced with J-Link:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v6x --jlink
```

Reset your target and start the capture:

```
(gdb) px4_trace_swo_stm32h7 <TER_REG> <SWO_FREQ[Hz]>
(gdb) continue
```

- Values for `<TER_REG>` are as described in [TER_REG](#ter_reg).
- The value of `<SWO_FREQ>` should be ≤20MHz to get reliable tracing.


### TER_REG

The `<TER_REG>` parameter defines which stimulus ports are enabled for
ITM and therefore which information will be included in the trace.
The stimulus port numbers are defined in the enum contained in
[itm.h](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/patch/data/itm.h).
Enabling stimulus port `i` requires setting bit `i` of the `TER_REG` parameter.

Useful values are:
- Task information: `0x0000000F`.
- Workqueue scheduling: `0x00000010`.
- Semaphore profiling: `0x000000E0`.
- Heap profiling: `0x00000F00`.
- DMA profiling: `0x00007000`.
- All optional user channels: `0xFFFF0000`.

As described above, they can be combined with a `bitwise or` to get combinations. For example:
- Task information + Workqueue scheduling: `0x0000001F`.


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
build/orbetto -C 216000 -f path/to/trace.swo -e path/to/fmu.elf
# FMUv6x runs at 480MHz
build/orbetto -C 480000 -f path/to/trace.swo -e path/to/fmu.elf
```

You should now have a `orbetto.perf` file that you can drag into
[the Perfetto UI](https://ui.perfetto.dev).
