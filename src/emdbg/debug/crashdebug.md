# CrashDebug Post-Mortem Analysis

[CrashDebug][] is a post-mortem debugging tool for Cortex-M microcontrollers.
You can create core dumps from GDB using the `px4_coredump` command (see
`emdbg.debug.gdb`).

```sh
python3 -m emdbg.debug.gdb -py --elf path/to/firmware.elf crashdebug --dump coredump.txt
```


## Analyzing Hardfault Logs

PX4 generated log files in case a hardfault is detected, which can be passed
directly to this backend to be converted on the fly by `emdbg.analyze.hardfault`.

```
$ python3.8 -m emdbg.debug.gdb --elf px4_fmu-v5x_default.elf -py crashdebug --dump hardfault.log
memset (s=0x0, c=0, n=80) at string/lib_memset.c:126
(gdb) backtrace
#0  memset (s=0x0, c=0, n=80) at string/lib_memset.c:126
#1  0x00000000 in ?? ()
Backtrace stopped: previous frame identical to this frame (corrupt stack?)
```

> **Note**  
> The hardfault log only contains a copy of the stack and registers. The
> converter fills unknown memory with the `0xfeedc0de` value, which may then
> display wrong or incomplete results in some of the GDB plugins. Keep this in
> mind when analyzing a hardfault.

In this example, the backtrace is broken, however, by inspecting the registers
you can see a valid location in the link register (LR) and manually inspect it:

```
(gdb) info registers
r0             0x0                 0
r1             0x0                 0
r2             0x50                80
r3             0x0                 0
r4             0x70                112
r5             0x0                 0
r6             0x0                 0
r7             0x18                24
r8             0x2001a660          536979040
r9             0x20044434          537150516
r10            0x0                 0
r11            0x0                 0
r12            0x70                112
sp             0x2001a600          0x2001a600
lr             0x817f17f           135786879
pc             0x8019f30           0x8019f30 <memset+120>
xpsr           0x21000200          553648640
fpscr          0xfeedc0de          -17973026
msp            0x2001a600          536978944
psp            0x2001a600          536978944
(gdb) info symbol 0x817f17f
uORB::DeviceNode::write(file*, char const*, unsigned int) + 435 in section .text
```

To understand the actual hardfault reason, use `arm scb /h` to show the
descriptions of the bit fields:

```
(gdb) arm scb /h
CFSR             = 00000400          // Configurable Fault Status Register
    MMFSR          ......00 - 00     // MemManage Fault Status Register
    BFSR           ....04.. - 04     // BusFault Status Register
    IMPRECISERR    .....4.. - 1      // Indicates if imprecise data access error has occurred.
    UFSR           0000.... - 0000   // UsageFault Status Register
HFSR             = 40000000          // HardFault Status Register
    FORCED         4....... - 1      // Indicates that a fault with configurable priority has been escalated to a HardFault exception.
DFSR             = 00000000          // Debug Fault Status Register
MMFAR            = 00000000          // MemManage Fault Address Register
BFAR             = 00000000          // BusFault Address Register
AFSR             = 00000000          // Auxiliary Fault Status Register
ABFSR - M7       = 00000308          // Auxiliary Bus Fault Status - Cortex M7
        AXIMTYPE   .....3.. - DECERR // Indicates the type of fault on the AXIM interface
    AXIM           .......8 - 1      // Asynchronous fault on AXIM interface
```

In this example, an imprecise, asynchronous bus fault has occurred on the AXIM
interface. Together with the backtrace and register information we can interpret
this error as a write to address zero inside the `memset` function, which was
passed a NULL pointer from inside `uORB::DeviceNode::write`.


## Installation

You need to have the [platform-specific `CrashDebug` binary][binary] available
in your path.

### Ubuntu

```sh
sudo curl -L https://github.com/adamgreen/CrashDebug/raw/master/bins/lin64/CrashDebug \
          -o /usr/bin/CrashDebug
sudo chmod +x /usr/bin/CrashDebug
```

### macOS

```sh
curl -L https://github.com/adamgreen/CrashDebug/raw/master/bins/osx64/CrashDebug \
     -o $HOMEBREW_PREFIX/bin/CrashDebug
# Clear the quarantine flag
sudo xattr -r -d com.apple.quarantine $HOMEBREW_PREFIX/bin/CrashDebug
```

Alternatively you can specify the binary path in your environment:

```sh
export PX4_CRASHDEBUG_BINARY=path/to/CrashDebug
```

> **Note**
> You need to have the Rosetta emulation layer installed on ARM64 macOS:
> ```sh
> softwareupdate --install-rosetta --agree-to-license
> ```

[crashdebug]: https://github.com/adamgreen/CrashDebug
[binary]: https://github.com/adamgreen/CrashDebug/tree/master/bins
