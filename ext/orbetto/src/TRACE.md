# Mortrall: NuttX Instrumentation with Perfetto and Instruction Trace

We can trace the NuttX scheduler with half cpu speed by
streaming the ETM debug trace over the parallel TRACE pins and capturing it to a file.

The Mortrall class decodes the ETM packets and generates a CallStack which can be visualized perfetto.
This includes Thread-switching and Exception detection to be able to follow the
execution on the corresponding Skynode (either PX4_V6x or PX4_V5x) very precisely.

![](https://github.com/niklaut/orbetto-support-files/blob/main/perfetto_callstack.png)

The structure of the code is based on the mortem module from orbuculum, but has been heavily modified to
fit to our needs. There have also been many fixes in loadelf and traceDecoder_etm4.

## Capture Trace:

Use OrbTrace for enabling TRACE pin output on the FMU.

Note: Data accumulates very quickly. When you want to display the full CallStack in perfetto trace less than a second.

### FMUv5x

Launch GDB inside your PX4-Autopilot source code directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v5x --orbtrace
```

Reset your target and start the capture:

```
(gdb) px4_etm_trace_tpiu_swo_stm32f7
(gdb) continue
```


### FMUv6x

Launch GDB inside your PX4-Autopilot source code directory:

```sh
# cd PX4-Autopilot
python3 -m emdbg.bench.fmu --target px4_fmu-v6x --jlink
```

Reset your target and start the capture:

```
(gdb) px4_etm_trace_tpiu_swo_stm32h7
(gdb) continue
```


### Visualization

To convert the `trace.swo` binary file to the Perfetto format, call the
`orbetto` program:

```sh
# cd embedded-debug-tools/ext/orbetto
build/orbetto -f path/to/trace.swo -e path/to/fmu.elf -b path/to/fmu_bootloader.elf -t 1
# use -v 3 to show advanced debug data that also prints instructions
# use -a to set a cycle count threshold from which verbose starts printing
```

If the trace.swo files contains instruction data, mortrall is automatically initialized and
generates a CallStack in perfbuf file.
You should now have a `orbetto.perf` file that you can drag into
[the Perfetto UI](https://ui.perfetto.dev).

## Known Issues

There are a couple of things you need to be aware of when using this tool.

### Hardware limitations (Skynode)

When Tracing Skynode V6x there some things that need to be considered regarding clock speed.
It is also important to know that there are two main configurations when tracing instructions.
There is implicit and explicit tracing, which can be set in the cortex_m.gdb file (implicit = startETM; explicit = startETM 1).
When tracing implicit the minimum amount of trace data is transmitted. This mainly refers the amount
of address packet, which basically transmit the current PC value (there are different formats).
When traced implicitly address packets are only send when there is no other way of following a branch.
During explicit tracing the address is transmitted after every jump, which results in a more robust trace and can
theoretically be analyzed starting at any point.

#### V5x

Unfortunately, it seems like during the design of the skynode no one thought of using the trace lines. Because of that, the PinOuts of
the chip are multipurpose. It is very important to remove the 3 LEDs from the Data lines. Their non-linear (I-V) characteristics
makes tracing of high frequency instruction data impossible. However, when removing the LEDs the resulting stubs can cause unwanted reflections,
which harms signal integrity.
Additionally, the trace lines are not length matched. Especially, the nArmed pin is also connected to one of the trace lines, which results in
three times the length than all other lines.
We roughly estimated that these issues are not too bad as long as you stay under 100Mhz of tracing.

The following signals have been observed with a Oscilloscope and a clock freq of 50Mhz after removing the LEDs:

![](https://github.com/niklaut/orbetto-support-files/blob/main/SCR17.BMP)

As the STM32F7 does only have a very small trace buffer (no ETF), explicit tracing only works when increasing the cpu prescaler in
board.h to 8 and also disable I and D cache to further slow down the cpu.
Implicit tracing instead only needs the increased prescaler, but still has a couple (~50) overflows when tracing which only happen
during initialization of PX4. This probably only happens when there are a lot of thread switches during PX4 init, which causes a burst in
address and branch packets. 

#### V6x

With V6x (STM32H7) Skynode hardware issues stay nearly the same.

However inside the STM we now have a ETF (Embedded Trace FIFO) of 4 kByte, which buffers the trace data during bursts.
Additionally, the clock sources of cpu and tracing having different prescalers so they can be set seperately.
The trace clk has to have a prescaler of 16 be within the hardware signale integrity limitations.
For the cpu clock we at least need a prescaler of 4 to get a correct callStack with a small amount of overflows.
With a prescaler of 8 there a no more overflows.

Note: V6x has only been tested with implicit traces.


### Perfetto

Because of memory limitations in the Perfetto UI (both local and web-interface) only a very short trace can be
visualized (less than: 25mB of trace data -> 300mB of perfbuf).

If you already know which Thread you want to monitor this problem can be solved by only displaying the corresponding Thread
as it is very unlikely that you need to see the full CallStack. (This is not implemented yet but can be easily added)

As mentioned, the decoding process in Mortrall makes it possible to track every executed instruction and jump precisely.
However, the python trace processor as well as the UI have a memory limitation which makes it impossible to further use
this information (regression testing, fuzzing, etc.) within the perfbuf format.
To circumvent this problem for now a additional library has been added called CRoaring. This library encodes all executed
Program Counters into a Bitmap. This library also has a python interface for further analysis of this data.
A description of how this has been used can be found in the METRIC.md readme.

Note: Unfortunately, the batch processor of perfetto does not help in this case, as it only allows for parallel decoding
of multiple perfbuf files (meaning many different traces) and not with one very big.

### NuttX

The computation of the CallStack is tightly coupled to the way NuttX handles thread switching. This means it is very likely
that this does not work for any other RTOS's.