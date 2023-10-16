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
    - [SEGGER J-Link](https://www.segger.com/products/debug-probes/j-link/): BASE Compact, EDU Mini.
    - [OpenOCD](https://openocd.org): [STMicro STLinkv3](https://www.st.com/en/development-tools/stlink-v3minie.html).
    - Coredump: [CrashDebug](https://github.com/adamgreen/CrashDebug) with support for PX4 Hardfault logs.
- Trace Probes: ITM/DWT/ETM over TRACE.
    - [Orbcode ORBTrace mini](https://orbcode.org/orbtrace-mini).
    - [SEGGER J-Trace](https://www.segger.com/products/debug-probes/j-trace/models/j-trace/) (planned).
- [GDB Debugger](https://developer.arm.com/Tools%20and%20Software/GNU%20Toolchain).
    - Automatic management of debug probe drivers.
    - Remote interfacing via [GDB/MI](https://github.com/cs01/pygdbmi) and RPyC.
    - Plugins via [GDB Python API](https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html).
    - [User commands for PX4 and NuttX](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/debug/gdb.md#user-commands).
        - Task information.
        - Task switching to inspect call stack.
        - Coredumping of memories and peripherals.
        - GPIO state visualization.
        - Backtrace generation.
        - Register state visualization using SVD files.
        - Register access watching and difference visualization.
    - Hardfault trapping with immediate backtrace.
- [Real-time instrumentation using ITM/DWT](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto).
    - Up to 2MB/s SWO capture via STLinkv3, 3MB/s via JLink.
    - Visualization of task switching and interrupts via [perfetto](https://perfetto.dev).
    - Latency measurement of scheduler and task priorities.
    - Heap usage tracking via malloc, free, realloc, alignmem.
    - Nanosecond resolution with very little runtime overhead.
- Patch Manager for out-of-tree modifications.
- Power Switch.
    - Yocto USB Relay.
- Logic Analyzer and Waveform Generator.
    - [Digilent Analog Discovery 2](https://digilent.com/reference/test-and-measurement/analog-discovery-2/start) via Python API.
    - [Sigrok](https://sigrok.org/wiki/Main_Page) (prototyped).
    - Visualization via [perfetto](https://perfetto.dev) (planned).
- Serial Protocols.
    - NuttX NSH command prompt.
- Hardware configuration.
    - [FMUv5x and FMUv6x](https://docs.px4.io/main/en/flight_controller/autopilot_pixhawk_standard.html).

A number of GDB and NSH scripting examples for test automation can be found in
the `scripts` folder.


## Presentations

### Debugging Microcontrollers

Presented at Chaos Communication Camp by Niklas Hauser on 2023-08-18.

[![](https://static.media.ccc.de/media/conferences/camp2023/57321-4a4f8363-865f-52b7-b236-3b9b73aa2ad7_preview.jpg)](https://media.ccc.de/v/camp2023-57321-debugging_microcontrollers)

### Debugging and Profiling NuttX and PX4

Presented at the NuttX International Workshop by Niklas Hauser on 2023-09-29.

[![](https://i3.ytimg.com/vi/_k1f4F2JVBA/maxresdefault.jpg)](https://www.youtube.com/watch?v=_k1f4F2JVBA)

## Installation

The latest version is hosted on PyPi and can be installed via pip:

```sh
pip3 install emdbg
```

You also need to install other command line tools depending on what you use:

- Debugger: [`arm-none-eabi-gdb-py3`](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/debug/gdb.md#installation).
- Debug probes: [J-Link](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/debug/jlink.md#installation),
                [OpenOCD](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/debug/openocd.md#installation),
                [CrashDebug](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/debug/crashdebug.md#installation).
- Analysis: [graphviz](https://github.com/Auterion/embedded-debug-tools/blob/main/src/emdbg/analyze/callgraph.md#installation)


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
You can browse the API documentation locally using the `pdoc` library:

```sh
pdoc emdbg
# pdoc server ready at http://localhost:8080
```


## Development

For development, checkout the repository locally, then install with the `-e`
flag, which symlinks the relevant files into the package path:

```sh
cd embedded-debug-tools
pip3 install -e ".[all]"
```
