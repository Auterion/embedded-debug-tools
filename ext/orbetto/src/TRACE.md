# Mortrall: NuttX instrumentation with Perfetto and Instruction Trace

We can trace the NuttX scheduler at half CPU speed by streaming the ETM debug
trace over the parallel TRACE pins and capturing it to a file.

The Mortrall class decodes the ETM packets and generates a CallStack that can be
visualized with Perfetto. This includes thread switching and exception
detection in order to be able to follow the code execution on the corresponding
PX4 FMUv5x or FMUv6x.

![](https://github.com/niklaut/orbetto-support-files/blob/main/perfetto_callstack.png)

The structure of the code is based on the mortem module from orbuculum, but has
been heavily modified to suit our needs. There have also been many fixes in
loadelf and traceDecoder_etm4.


## Capture the trace

Use OrbTrace to enable the TRACE pin output on the FMU.

> [!TIP]  
> Data accumulates very fast. If you want to see the whole CallStack in
> Perfetto Trace, trace less than a second.


### FMUv5x

Start GDB in your PX4 Autopilot source directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v5x --orbtrace
```

Reset the target and start the capture:

```
(gdb) px4_etm_trace_tpiu_swo_stm32f7 <TER_REG>
(gdb) Continue
```

Values for `<TER_REG>` are as described in: [TER_REG](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto/README.md#ter_reg).


### FMUv6x

Start GDB in your PX4 Autopilot source directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v6x --orbtrace
```

Reset the target and start the capture. You might need to power cycle the target:

```
(gdb) px4_etm_trace_tpiu_swo_stm32h7 <TER_REG>
(gdb) Continue
```

Values for `<TER_REG>` are as described in: [TER_REG](https://github.com/Auterion/embedded-debug-tools/blob/main/ext/orbetto/README.md#ter_reg).


### Visualization

To convert the `trace.swo` binary to Perfetto format call Orbetto:

```sh
# cd embedded-debug-tools/ext/orbetto
build/orbetto -f path/to/trace.swo -e path/to/fmu.elf -b path/to/fmu_bootloader.elf -t 1
# Use -v 3 to show advanced debugging data that also prints instructions
# Use -a to set a cycle count threshold at which verbose printing starts
```

If the `trace.swo` files contain instruction data, Mortrall is automatically
initialized and and creates a CallStack in the Protobuf file. You should now
have an `orbetto.perf` file that you can drag into the
[Perfetto user interface](https://ui.perfetto.dev).


## Limitations

There are a few things you need to be aware of when using this tool.


### Hardware

It is  important to know that there are two main configurations when tracing
instructions. There is implicit and explicit tracing, which can be set in the
`cortex_m.gdb` file (implicit = `startETM`; explicit = `startETM 1`). With
implicit tracing, the minimum amount of trace data is sent. This mainly refers
to the number of address packets, which basically transmit the current PC
value (there are different formats). With implicit tracing, address packets are
only sent if there is no other way to follow a branch. With explicit tracing,
the address is sent after each branch, resulting in a more robust trace that
can be theoretically be analyzed from any point.


#### FMUv5x

Unfortunately, the trace pinouts of the chip are multipurpose. It is very
important to remove the 3 LEDs from the data lines. Their non-linear
(I-V) characteristics makes it impossible to trace high frequency instruction
data. However, if the LEDs are removed, the resulting stubs can cause unwanted
reflections, which compromises signal integrity. In addition, the trace lines
are not matched in length. In particular, the `nARMED` pin is also connected to
one of the trace lines, making it three times the length of all the other
traces. We have roughly estimated that these problems are not too bad as long
as you stay under 100MHz when tracing.

The following signals have been observed with an oscilloscope and a clock
frequency of 50Mhz after removing the LEDs:

![](https://github.com/niklaut/orbetto-support-files/blob/main/SCR17.BMP)

Since the STM32F7 has only a very small trace buffer (no ETF), explicit tracing
only works if you increase the CPU prescaler in `board.h` to 8 and also disable
the instruction and data cache to further slow down the CPU. Implicit tracing
instead only needs the increased prescaler, but still has a few (~50) overflows
when tracing. This probably only happens when there are a lot of thread
switches during PX4 initialization, which causes a burst in address and branch
packets.


#### FMUv6x

With FMUv6x (STM32H7), the Skynode hardware issues remain much the same.

However, we now have a 4kByte ETF (Embedded Trace FIFO) inside the STM, which
buffers the trace data during bursts. In addition, the CPU and trace clock
sources have different prescalers so that they can be set separately. The trace
clock must have a prescaler of 16 to stay within the hardware signal integrity
limits. For the CPU clock we need at least a prescaler of 4 (=half max CPU
speed) to get a correct call stack with a small amount of overflow. With a
prescaler of 8 there will be no overflows.

> [!NOTE]  
> FMUv6x has only been tested with implicit traces.


### Perfetto

Due to memory limitations in the Perfetto UI (both local and web interface),
only a very short trace can be visualized (~25MB of trace data results in
~300MB of Protobuf).

If you already know which thread you want to monitor, this problem can be solved
by displaying only the corresponding thread as it is very unlikely that you
need to see the full CallStack. This is not implemented yet, but can easily be
added.

As mentioned above, the decoding process in Mortrall makes it possible to trace
every executed instruction and jump precisely. However, both the Python trace
processor and the UI have a memory limitation that makes it impossible to use
this information further (regression testing, fuzzing, etc.) within the
Protobuf format. To work around this problem for now, an additional library
called CRoaring has been added. This library encodes all executed program
counter values into a bitmap. It also has a Python interface for further
analysis of this data. A description of how to use this can be found in
[METRICS.md](../metrics/METRICS.md).

> [!NOTE]  
> Unfortunately, the Perfetto batch processor does not help in this case, as
> it only allows parallel decoding of multiple Protobuf files (ie. many
> different traces) and not with a very large one.


### NuttX

The computation of the CallStack is tightly coupled to the way NuttX handles
thread switching. This means that it is very likely that this will not work for
any other RTOS without modifications.
