# Embedded Debug Tools

The emdbg library connects several software and hardware debugging tools
together in a user friendly Python package to more easily enable advanced use
cases for ARM Cortex-M microcontrollers and related devices.

The library orchestrates the launch and configuration of hardware debug and
trace probes, debuggers, logic analyzers, and waveform generators and provides
analysis tools, converters, and plugins to provide significant insight into the
software and hardware state during or after execution.

The main focus of this project is the debugging of the PX4 Autopilot firmware
running the NuttX RTOS on STM32 microcontrollers on the FMUv5x and FMUv6x
hardware inside the Auterion Skynode. However, the library is modular and the
tools are generic so that it can also be used for other firmware either
out-of-box or with small adaptations.

emdbg is maintained by [@niklaut](https://github.com/niklaut) from
[Auterion](https://auterion.com).

## Features

- Debug Probes: SWD and ITM/DWT over SWO.
    - [SEGGER J-Link](https://www.segger.com/products/debug-probes/j-link/): BASE Compact (3MB/s), EDU Mini.
    - [STMicro STLink-v3 MINIE](https://www.st.com/en/development-tools/stlink-v3minie.html): (2MB/s).
    - [Orbcode ORBTrace mini](https://orbcode.org/orbtrace-mini): SWO (6MB/s).
    - Coredump via [CrashDebug](https://github.com/adamgreen/CrashDebug) with support for PX4 Hardfault logs.
- Trace Probes: ITM/DWT/ETM over TRACE.
    - [Orbcode ORBTrace mini](https://orbcode.org/orbtrace-mini): (50MB/s).
- [GDB Debugger](https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain).
    - Automatic management of debug probe drivers.
    - Remote interfacing via [GDB/MI](https://github.com/cs01/pygdbmi) and RPyC.
    - Plugins via [GDB Python API](https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html).
    - [User commands for PX4 and NuttX](https://auterion.github.io/embedded-debug-tools/emdbg/debug/gdb.html#user-commands).
    - Hardfault trapping with immediate backtrace.
- [Real-time instrumentation using ITM/DWT](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto).
    - Visualization of entire RTOS state via [perfetto](https://perfetto.dev).
    - Nanosecond resolution with very little runtime overhead.
- [Real-time instruction trace using ETM](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto/src/TRACE.md).
    - Visualization of callstacks via [perfetto](https://perfetto.dev).
    - Generation of [metrics from trace via PerfettoSQL](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto/metrics/METRICS.md).
- Patch Manager for out-of-tree modifications.
- Power Switch.
    - Yocto USB Relay.
- Logic Analyzer and Waveform Generator.
    - [Digilent Analog Discovery 2](https://digilent.com/reference/test-and-measurement/analog-discovery-2/start) via Python API.
    - [Glasgow Digital Interface Explorer](https://glasgow-embedded.org/) (planned).
- Serial Protocols.
    - NuttX NSH command prompt.
- Hardware configuration.
    - [FMUv5x and FMUv6x](https://docs.px4.io/main/en/flight_controller/autopilot_pixhawk_standard.html).

A number of GDB and NSH scripting examples for test automation can be found in
the `scripts` folder.


## Presentations

Sorted in reverse chronological order.

### Utilizing Instruction Tracing to Analyze PX4 at Runtime

Presented at [Auterion](https://auterion.com) by [Lukas von Briel](https://www.linkedin.com/in/lvb2000) on 2024-10-31.

<a href="https://www.youtube.com/watch?v=sJ5pnPrWA30"><img src="https://i.ytimg.com/vi/sJ5pnPrWA30/maxresdefault.jpg" width="100%"/></a>

[Slides with Notes](https://salkinium.com/talks/auterion24_instruction_tracing.pdf).

### Analyzing Cortex-M Firmware with the Perfetto Trace Processor

Presented at [emBO++](https://embo.io) by Niklas Hauser on 2024-03-15.

<a href="https://www.youtube.com/watch?v=FIStxUz2ERY&t=108s"><img src="https://i.ytimg.com/vi/FIStxUz2ERY/maxresdefault.jpg" width="100%"/></a>

[Slides with Notes](https://salkinium.com/talks/embo24_perfetto.pdf).

### Debugging PX4

Presented at the [PX4 Developer Summit](https://events.linuxfoundation.org/px4-developer-summit) by Niklas Hauser on 2023-10-22.

<a href="https://www.youtube.com/watch?v=1c4TqEn3MZ0"><img src="https://i.ytimg.com/vi/1c4TqEn3MZ0/maxresdefault.jpg" width="100%"/></a>

[Slides with Notes](https://salkinium.com/talks/px4summit23_debugging_px4.pdf).

### Debugging and Profiling NuttX and PX4

Presented at the [NuttX International Workshop](https://events.nuttx.apache.org/index.php/nuttx-international-workshop-2023) by Niklas Hauser on 2023-09-29.

<a href="https://www.youtube.com/watch?v=_k1f4F2JVBA"><img src="https://i3.ytimg.com/vi/_k1f4F2JVBA/maxresdefault.jpg" width="100%"/></a>

### Debugging Microcontrollers

Presented at [Chaos Communication Camp](https://events.ccc.de/camp/2023/) by Niklas Hauser on 2023-08-18.

<a href="https://media.ccc.de/v/camp2023-57321-debugging_microcontrollers"><img src="https://static.media.ccc.de/media/conferences/camp2023/57321-4a4f8363-865f-52b7-b236-3b9b73aa2ad7_preview.jpg" width="100%"/></a>

[Slides with Notes](https://salkinium.com/talks/cccamp23_debugging_microcontrollers.pdf).

## Installation

The latest version is hosted on PyPi and can be installed via pip:

```sh
pip3 install emdbg
```

You also need to install other command line tools depending on what you use:

- Debugger: [`arm-none-eabi-gdb-py3`](https://auterion.github.io/embedded-debug-tools/emdbg/debug/gdb.html#installation).
- Debug probes: [J-Link](https://auterion.github.io/embedded-debug-tools/emdbg/debug/jlink.html#installation),
                [OpenOCD](https://auterion.github.io/embedded-debug-tools/emdbg/debug/openocd.html#installation),
                [CrashDebug](https://auterion.github.io/embedded-debug-tools/emdbg/debug/crashdebug.html#installation).
- Analysis: [graphviz](https://auterion.github.io/embedded-debug-tools/emdbg/analyze/callgraph.html#installation)


## Usage

Most modules have their own command-line interface. This library therefore has
many entry points which can be called using `python3 -m emdbg.{module}`.
The individual command line usage is documented in each module.
The most important modules are `emdbg.debug.gdb` and `emdbg.bench.fmu`:

For example, launching GDB with TUI using a J-Link debug probe:

```sh
python3 -m emdbg.debug.gdb --elf path/to/firmware.elf --ui=tui jlink -device STM32F765II
```


## Documentation

Most important user guides are available as Markdown files in the repository.
You can browse the latest API documentation online at
[auterion.github.io/embedded-debug-tools](https://auterion.github.io/embedded-debug-tools).


## Development

For development, checkout the repository locally, then install with the `-e`
flag, which symlinks the relevant files into the package path:

```sh
cd embedded-debug-tools
pip3 install -e ".[all]"
```

You can also work on the documentation locally via `pdoc`:

```sh
pdoc emdbg
# pdoc server ready at http://localhost:8080
```
