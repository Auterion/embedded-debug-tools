# GDB Debugger

This module manages the invocation of GDB in various contexts for user
interaction or automated scripting.


## Installation

Unfortunately, the official `arm-none-eabi-gcc` v9 and v10 from ARM only come
with the Python 2.7 API, whose support has reached end-of-life in 2020.
The newer v11 and v12 versions removed Python support altogether.

Therefore you need to install a third-party toolchain. We tested and recommend
the [xpack v12 toolchain][xpack], since it has been adapted from the official
compiler sources from ARM to include a standalone Python 3.11 runtime and thus
is the closest we have to an official toolchain.
We strongly recommend to *only* symlink the `arm-none-eabi-gdb-py3` binary into
your path, and keep the remaining `arm-none-eabi-gcc` at v9 as done for PX4.

### Ubuntu

```sh
sudo install -d -o $USER /opt/xpack

curl -L https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v12.2.1-1.2/xpack-arm-none-eabi-gcc-12.2.1-1.2-linux-x64.tar.gz | \
        tar -xvzf - -C /opt/xpack/
# Only link the -py3 into your path
ln -s /opt/xpack/xpack-arm-none-eabi-gcc-12.2.1-1.2/bin/arm-none-eabi-gdb-py3 \
      /opt/gcc-arm-none-eabi-9-2020-q2-update/bin/arm-none-eabi-gdb-py3
```

### macOS

On macOS you additionally need to clear the quarantine flags after expansion:

```sh
sudo install -d -o $USER /opt/xpack

if [[ $(arch) == 'arm64' ]]; then export gdbarch='arm'; else export gdbarch='x'; fi
curl -L "https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v12.2.1-1.2/xpack-arm-none-eabi-gcc-12.2.1-1.2-darwin-${gdbarch}64.tar.gz" | \
        tar -xvzf - -C /opt/xpack/

# Clear the quarantine flag
sudo xattr -r -d com.apple.quarantine /opt/xpack/

# Only link the -py3 into your path
ln -s /opt/xpack/xpack-arm-none-eabi-gcc-12.2.1-1.2/bin/arm-none-eabi-gdb-py3 \
      $HOMEBREW_PREFIX/bin/arm-none-eabi-gdb-py3
```


## Command Line Interface

These commands runs the probe in the background and launches GDB in the
foreground either using the Text User Interface (TUI) or the web-based [GDBGUI][].

Launch GDB and connect it to a running extended remote server:

```sh
python3 -m emdbg.debug.gdb --elf path/to/firmware.elf --ui=cmd remote --port IP_ADDRESS:2331
```

Launch GDB and connect it to a J-Link backend:

```sh
python3 -m emdbg.debug.gdb --elf path/to/firmware.elf --ui=tui jlink -device STM32F765II
```

If provided with the `--python` flag, then the Python GDB is used and the functionality
of `emdbg.debug.px4` is made available inside GDB as user commands:

```sh
python3 -m emdbg.debug.gdb --python --elf path/to/firmware.elf jlink -device STM32F765II
```

To access peripheral registers in the debugger, you must specify the CMSIS-SVD files:

```sh
python3 -m emdbg.debug.gdb --python --elf path/to/firmware.elf --svd path/to/STM32F7x5.svd jlink -device STM32F765II
```

Coredumps can be analyzed offline as well (see `emdbg.debug.crashdebug`):

```sh
python3 -m emdbg.debug.gdb -py --elf path/to/firmware.elf crashdebug --dump coredump.txt
# This also works with PX4 hardfault logs
python3 -m emdbg.debug.gdb -py --elf path/to/firmware.elf crashdebug --dump px4_hardfault.log
```


## User Commands

GDB has a [Python API][gdbpy] for providing much deeper access than given by the
standard scripting API. The `emdbg.debug.px4` modules provide a library of
tools for analyzing PX4 at debug time.

You can call the modules directly:

```
(gdb) python print(px4.all_tasks_as_table(gdb))
```

> **Note**  
> The `emdbg.debug.px4` tools are accessible inside the GDB command prompt
> only as a top-level `px4` Python module to avoid loading in all of the
> `emdbg` modules.


For convenience, several user commands wrap our Python plugins:

### px4_discover

Shows information about the connected device.

```
(gdb) px4_discover
                                ╷               ╷        ╷                     ╷
  Device                        │ Revision      │ Flash  │ Package             │ UID
 ═══════════════════════════════╪═══════════════╪════════╪═════════════════════╪══════════════════════════
  0x451: STM32F76xx, STM32F77xx │ 0x1001: rev Z │ 2048kB │ LQFP208 or TFBGA216 │ 20373658375650140045002c
                                ╵               ╵        ╵                     ╵
```

### px4_reset

Resets and halts the device using the correct command for the backend.


### px4_tasks

```
px4_tasks [--files]
```

Pretty prints a table of all NuttX threads and their state with optional file
handle names. This is similar to the NSH command `top`, however, does not
require a live system to work. You inspect other thread stacks by switching to
it using `px4_switch_task [PID]`.

```
(gdb) px4_tasks
                ╷      ╷                        ╷                 ╷         ╷        ╷       ╷       ╷      ╷      ╷     ╷       ╷
                │      │                        │                 │         │        │ Stack │ Avail │      │      │     │       │
  struct tcb_s* │  pid │ Task Name              │ Location        │ CPU(ms) │ CPU(%) │ Usage │ Stack │ Prio │ Base │ FDs │ State │ Waiting For
 ═══════════════╪══════╪════════════════════════╪═════════════════╪═════════╪════════╪═══════╪═══════╪══════╪══════╪═════╪═══════╪══════════════════════════════════════
     0x2002673c │    0 │ Idle Task              │ nx_start        │   10256 │   53.8 │   398 │   726 │    0 │    0 │   3 │ RUN   │
     0x2007c310 │    1 │ hpwork                 │ nxsem_wait      │       0 │    0.0 │   292 │  1224 │  249 │  249 │   3 │ w:sem │ 0x200208e8 -1 waiting
     0x2007cde0 │    2 │ lpwork                 │ nxsem_wait      │       6 │    0.0 │   500 │  1576 │   50 │   50 │   3 │ w:sem │ 0x200208fc -1 waiting
     0x2007da10 │    3 │ nsh_main               │ nxsem_wait      │       0 │    0.0 │  1980 │  3040 │  100 │  100 │   4 │ w:sem │ 0x20020594 -1 waiting
     0x2007f0c0 │    4 │ wq:manager             │ nxsem_wait      │       0 │    0.0 │   588 │  1232 │  255 │  255 │   5 │ w:sem │ 0x2007fce8 -1 waiting: 1x wq:manager
     0x2007fe20 │    5 │ wq:lp_default          │ nxsem_wait      │      74 │    0.4 │  1388 │  1896 │  205 │  205 │   5 │ w:sem │ 0x2000072c -1 waiting
     0x20001e40 │    6 │ Telnet daemon          │ nxsem_wait      │       0 │    0.0 │   556 │  1984 │  100 │  100 │   1 │ w:sem │ 0x20002ad0 -1 waiting
     0x20002f20 │    7 │ netinit                │ nxsem_wait      │       1 │    0.0 │   764 │  2024 │   49 │   49 │   4 │ w:sem │ 0x20027014 -1 waiting
     0x20004980 │   60 │ wq:hp_default          │ nxsem_wait      │     182 │    1.0 │  1052 │  1872 │  237 │  237 │   5 │ w:sem │ 0x20005c54 -1 waiting
     0x20005d10 │   63 │ wq:I2C3                │ nxsem_wait      │      62 │    0.3 │   736 │  2312 │  244 │  244 │   5 │ w:sem │ 0x200066bc -1 waiting
     0x200040e0 │   88 │ dataman                │ nxsem_wait      │       0 │    0.0 │  1068 │  1376 │   90 │   90 │   5 │ w:sem │ 0x200072d0 -1 waiting
     0x20007fb0 │  141 │ wq:ttyS5               │ nxsem_wait      │      95 │    0.6 │  1084 │  1704 │  229 │  229 │   5 │ w:sem │ 0x2000873c -1 waiting
     0x20005300 │  217 │ wq:SPI3                │ nxsem_wait      │     724 │    4.0 │  1484 │  2368 │  251 │  251 │   5 │ w:sem │ 0x2000a864 -1 waiting
     0x20005090 │  235 │ wq:SPI1                │ nxsem_wait      │     479 │    2.6 │  1780 │  2368 │  253 │  253 │   5 │ w:sem │ 0x2000c224 -1 waiting
     0x2000b5b0 │  250 │ wq:I2C4                │ nxsem_wait      │     100 │    0.5 │   960 │  2312 │  243 │  243 │   5 │ w:sem │ 0x2000cb4c -1 waiting
     0x2000d810 │  393 │ wq:nav_and_controllers │ nxsem_wait      │     516 │    3.0 │  1248 │  2216 │  242 │  242 │   5 │ w:sem │ 0x2000ff4c -1 waiting
     0x2000e170 │  394 │ wq:rate_ctrl           │ nxsem_wait      │     213 │    1.2 │  1532 │  3120 │  255 │  255 │   5 │ w:sem │ 0x20010ba4 -1 waiting
     0x200128a0 │  396 │ wq:INS0                │ nxsem_wait      │     956 │    5.2 │  4244 │  5976 │  241 │  241 │   5 │ w:sem │ 0x2001409c -1 waiting
     0x200149c0 │  398 │ wq:INS1                │ nxsem_wait      │     887 │    4.8 │  4244 │  5976 │  240 │  240 │   5 │ w:sem │ 0x200161bc -1 waiting
     0x20016430 │  400 │ commander              │ nxsig_timedwait │     242 │    1.3 │  1468 │  3192 │  140 │  140 │   5 │ w:sig │ signal
     0x20009ab0 │  403 │ ekf2                   │ nxsig_timedwait │     167 │    0.9 │  1300 │  2000 │  237 │  237 │   3 │ w:sig │ signal
     0x2003c0b0 │  411 │ mavlink_if0            │ nxsig_timedwait │    1327 │    7.3 │  1916 │  3064 │  100 │  100 │   5 │ w:sig │ signal
     0x20040890 │  413 │ mavlink_rcv_if0        │ nxsem_wait      │      89 │    0.5 │   212 │  6056 │  175 │  175 │   5 │ w:sem │ 0x20041ad8 -1 waiting
     0x2003baa0 │  625 │ gps                    │ nxsem_wait      │      11 │    0.1 │  1220 │  1936 │  205 │  205 │   4 │ w:sem │ 0x200436d0 -1 waiting
     0x20004dd0 │  786 │ mavlink_if1            │ nxsig_timedwait │     420 │    2.4 │  1916 │  3048 │  100 │  100 │   5 │ w:sig │ signal
     0x20046970 │  788 │ mavlink_rcv_if1        │ nxsem_wait      │      79 │    0.4 │   212 │  6056 │  175 │  175 │   5 │ w:sem │ 0x20047bb8 -1 waiting
     0x200439f0 │  894 │ mavlink_if2            │ nxsig_timedwait │     978 │    5.5 │  1860 │  3048 │  100 │  100 │   5 │ w:sig │ signal
     0x2004b270 │  904 │ mavlink_rcv_if2        │ nxsem_wait      │      72 │    0.4 │   212 │  6056 │  175 │  175 │   5 │ w:sem │ 0x2004c4b8 -1 waiting
     0x20042590 │  975 │ uxrce_dds_client       │ nxsem_wait      │       5 │    0.0 │   540 │  9920 │  100 │  100 │   4 │ w:sem │ 0x2004f8d0 -1 waiting
     0x20042850 │ 1014 │ navigator              │ nxsem_wait      │      26 │    0.1 │  1068 │  2104 │  105 │  105 │   7 │ w:sem │ 0x2004e250 -1 waiting
     0x2004d560 │ 1333 │ logger                 │ nxsem_wait      │      64 │    0.4 │  3116 │  3616 │  230 │  230 │   3 │ w:sem │ 0x20054720 -1 waiting
     0x200482a0 │ 1400 │ wq:uavcan              │ nxsem_wait      │     284 │    1.5 │  2252 │  3600 │  236 │  236 │   5 │ w:sem │ 0x20058784 -1 waiting
     0x2004e610 │ 1401 │ log_writer_file        │ nxsem_wait      │       0 │    0.0 │   388 │  1144 │   60 │   60 │   3 │ w:sem │ 0x2004ece0 -1 waiting
                ╵      ╵                        ╵                 ╵         ╵        ╵       ╵       ╵      ╵      ╵     ╵       ╵
Processes: 33 total, 1 running, 32 sleeping
CPU usage: 44.4% tasks, 1.8% sched, 53.8% idle
Uptime: 19.33s total, 0.62s interval
```


### px4_files

```
px4_files
```

Pretty prints a table of open files and their private data handle.

```
(gdb) px4_files
                ╷            ╷                              ╷
  struct inode* │ i_private* │ Name                         │ Tasks
 ═══════════════╪════════════╪══════════════════════════════╪═══════════════════════════════════════════════════════════════════════════════════════════════════════════
     0x2007c070 │ 0x20020570 │ console                      │ Idle Task, commander, dataman, gimbal, gps, hpwork, init, log_writer_file, logger, lpwork, mavlink_if0,
                │            │                              │ mavlink_if1, mavlink_if2, mavlink_rcv_if0, mavlink_rcv_if1, mavlink_rcv_if2, navigator, wq:I2C2, wq:I2C4,
                │            │                              │ wq:INS0, wq:SPI1, wq:SPI2, wq:SPI3, wq:ff_escs, wq:hp_default, wq:lp_default, wq:manager,
                │            │                              │ wq:nav_and_controllers, wq:rate_ctrl, wq:ttyS7
     0x2007f100 │            │ console_buf                  │ commander, dataman, gimbal, gps, init, log_writer_file, logger, mavlink_if0, mavlink_if1, mavlink_if2,
                │            │                              │ mavlink_rcv_if0, mavlink_rcv_if1, mavlink_rcv_if2, navigator, wq:I2C2, wq:I2C4, wq:INS0, wq:SPI1,
                │            │                              │ wq:SPI2, wq:SPI3, wq:ff_escs, wq:hp_default, wq:lp_default, wq:manager, wq:nav_and_controllers,
                │            │                              │ wq:rate_ctrl, wq:ttyS7
     0x2007c1c0 │ 0x200201d0 │ ttyS6                        │ mavlink_if1, mavlink_rcv_if1
     0x2007c130 │ 0x20020000 │ ttyS3                        │ mavlink_if2, mavlink_rcv_if2
     0x20001600 │ 0x20021228 │ can0                         │ wq:I2C2, wq:I2C4, wq:INS0, wq:SPI1, wq:SPI2, wq:SPI3, wq:ff_escs, wq:hp_default, wq:lp_default,
                │            │                              │ wq:manager, wq:nav_and_controllers, wq:rate_ctrl, wq:ttyS7
     0x20001730 │ 0x2002ad00 │ gpin4                        │ wq:I2C2, wq:I2C4, wq:INS0, wq:SPI1, wq:SPI2, wq:SPI3, wq:ff_escs, wq:hp_default, wq:lp_default,
                │            │                              │ wq:manager, wq:nav_and_controllers, wq:rate_ctrl, wq:ttyS7
     0x20001760 │ 0x2002ad3c │ gpin5                        │ wq:I2C2, wq:I2C4, wq:INS0, wq:SPI1, wq:SPI2, wq:SPI3, wq:ff_escs, wq:hp_default, wq:lp_default,
                │            │                              │ wq:manager, wq:nav_and_controllers, wq:rate_ctrl, wq:ttyS7
     0x20002170 │ 0x200021a0 │ microsd                      │ commander, dataman, log_writer_file, logger
     0x2005e720 │ 0x2005e6e0 │ pipe1                        │ mavlink, mavlink_shell
     0x2005e510 │ 0x2005e650 │ pipe0                        │ mavlink, mavlink_if0, mavlink_rcv_if0, mavlink_shell
     0x2007c160 │ 0x200200e8 │ ttyS4                        │ mavlink_if0, mavlink_rcv_if0
     0x2001c7b0 │ 0x2001c740 │ vehicle_local_position0      │ navigator
     0x2003a050 │ 0x2003a010 │ mission0                     │ navigator
     0x2001a920 │ 0x2001a8c0 │ vehicle_status0              │ navigator
     0x2000f520 │ 0x2003a190 │ vehicle_roi0                 │ gimbal
     0x20041010 │ 0x20040fa0 │ position_setpoint_triplet0   │ gimbal
     0x200410f0 │ 0x20041080 │ gimbal_manager_set_attitude0 │ gimbal
     0x2007c0a0 │ 0x200203a0 │ ttyS0                        │ gps
     0x200014b0 │ 0x20001490 │ led0                         │ commander
     0x2001a4c0 │ 0x2001a450 │ vehicle_command_ack0         │ commander
                ╵            ╵                              ╵
```


### px4_dmesg

```
px4_dmesg
```

Prints the dmesg buffer of PX4.

```
(gdb) px4_dmesg
$1 = ConsoleBuffer(2394B/4095B: [0 -> 2394]) =
HW arch: PX4_FMU_V6X
HW type: V6X010010
HW version: 0x010
HW revision: 0x010
PX4 git-hash: 1cac91d5a9d19dc081bc54d0ea2b7d26ed64c8d8
PX4 version: 1.14.0 40 (17694784)
PX4 git-branch: develop
Vendor version: 3.0.0 64 (50331712)
OS: NuttX
OS version: Release 11.0.0 (184549631)
OS git-hash: b25bc43cd81e257c5e63ac17c7c4331510584af6
Build datetime: Feb 23 2024 17:18:44
Build uri: localhost
Build variant: default
Toolchain: GNU GCC, 9.3.1 20200408 (release)
PX4GUID: 000600000000373833333430510d002c0045
```


### px4_perf

```
px4_perf [NAME] [-s {pointer,name,events,elapsed,average,least,most,rms,interval,first,last}]

options:
  NAME                  Regex filter for perf counter names.
  -s, --sort {pointer,name,events,elapsed,average,least,most,rms,interval,first,last},
                        Column name to sort the table by.
```

Pretty prints a table of all performance counters and their values.
You can regex filter for the names of counters and sort the table by column.

```
(gdb) px4_perf -s events
                  ╷                                                  ╷        ╷         ╷         ╷         ╷         ╷           ╷          ╷         ╷
  perf_ctr_count* │ Name                                             │ Events │ Elapsed │ Average │   Least │    Most │       RMS │ Interval │   First │  Last
 ═════════════════╪══════════════════════════════════════════════════╪════════╪═════════╪═════════╪═════════╪═════════╪═══════════╪══════════╪═════════╪═══════
       0x30013e60 │ mission_dm_cache_miss                            │      0 │         │         │         │         │           │          │         │
       0x3800af50 │ rc_update: cycle                                 │      0 │       - │       - │       - │       - │         - │          │         │
       0x3800af90 │ rc_update: cycle interval                        │      0 │         │       - │       - │       - │         - │        - │       - │     -
       0x3800c610 │ icm42688p: FIFO reset                            │      4 │         │         │         │         │           │          │         │
       0x38004600 │ param: get                                       │  20689 │         │         │         │         │           │          │         │
       0x24018870 │ param: find                                      │  27540 │         │         │         │         │           │          │         │
       0x3000de70 │ mavlink: tx run elapsed                          │  29431 │   2.9 s │  99.9µs │  54  µs │   2.7ms │  84.289µs │          │         │
       0x30002c90 │ mavlink: tx run elapsed                          │  29453 │   3.5 s │ 118.4µs │  64  µs │   1.6ms │  90.483µs │          │         │
       0x30014410 │ uavcan: cycle interval                           │  29462 │         │   3  ms │ 194  µs │  65.8ms │ 513.188µs │    1.5 m │   1.2 s │ 1.5 m
       0x38008910 │ board_adc: sample                                │  70952 │ 192.9ms │   2.7µs │   2  µs │ 850  µs │  13.039µs │          │         │
                  ╵                                                  ╵        ╵         ╵         ╵         ╵         ╵           ╵          ╵         ╵
```


### px4_switch_task

```
px4_switch_task PID
```

Saves the current execution environment and loads the target task environment.
You can use this to inspect the local stack and backtrace of other tasks even
when they are not running. The original execution environment is loaded
automatically on `continue` or `quit`.

> **Warning**  
> The original execution environment cannot be reset when GDB crashes!
> In that case, there will be memory corruption on the device.

```
(gdb) px4_switch_task 799
Switched to task 'mavlink_rcv_if0' (799).
(gdb) backtrace
#0  arm_switchcontext () at armv7-m/gnu/arm_switchcontext.S:79
#1  0x0800b3ce in nxsem_wait (sem=sem@entry=0x2003c3f0) at semaphore/sem_wait.c:155
#2  0x08175234 in nxsem_tickwait (sem=sem@entry=0x2003c3f0, start=1842, delay=delay@entry=10) at semaphore/sem_tickwait.c:122
#3  0x08170ca6 in nx_poll (fds=fds@entry=0x2003c464, nfds=nfds@entry=1, timeout=timeout@entry=10) at vfs/fs_poll.c:415
#4  0x08170dca in poll (fds=fds@entry=0x2003c464, nfds=nfds@entry=1, timeout=timeout@entry=10) at vfs/fs_poll.c:493
#5  0x080f944e in MavlinkReceiver::run (this=0x20038ff8, this@entry=<error reading variable: value has been optimized out>) at src/modules/mavlink/modules__mavlink_unity.cpp:12323
#6  0x080f9c96 in MavlinkReceiver::start_trampoline (context=<error reading variable: value has been optimized out>) at src/modules/mavlink/modules__mavlink_unity.cpp:12745
#7  0x08014904 in pthread_startup (entry=<optimized out>, arg=<optimized out>) at pthread/pthread_create.c:59
#8  0x00000000 in ?? ()
```

### px4_registers

```
px4_registers
```

Pretty prints a table with all register values.

```
(gdb) px4_registers
            ╷                  ╷                      ╷
  Name      │      Hexadecimal │              Decimal │                                                           Binary
 ═══════════╪══════════════════╪══════════════════════╪══════════════════════════════════════════════════════════════════
  r0        │                0 │                    0 │                                                                0
  r1        │         200267c4 │            537028548 │                                   100000000000100110011111000100
  r2        │         2007ccfc │            537382140 │                                   100000000001111100110011111100
  r3        │         200267c4 │            537028548 │                                   100000000000100110011111000100
  r4        │         2002673c │            537028412 │                                   100000000000100110011100111100
  r5        │         200267f4 │            537028596 │                                   100000000000100110011111110100
  r6        │         200267f0 │            537028592 │                                   100000000000100110011111110000
  r7        │         20026734 │            537028404 │                                   100000000000100110011100110100
  r8        │                0 │                    0 │                                                                0
  r9        │                0 │                    0 │                                                                0
  r10       │                0 │                    0 │                                                                0
  r11       │                0 │                    0 │                                                                0
  r12       │                0 │                    0 │                                                                0
  sp        │         20036b44 │            537094980 │                                   100000000000110110101101000100
  lr        │          800b14b │            134263115 │                                     1000000000001011000101001011
  pc        │          800b14a │            134263114 │                                     1000000000001011000101001010
  xpsr      │         41000000 │           1090519040 │                                  1000001000000000000000000000000
  d0        │                0 │                    0 │                                                                0
  ...       │              ... │                  ... │                                                              ...
  d15       │ ffffffff00000000 │ 18446744069414584320 │ 1111111111111111111111111111111100000000000000000000000000000000
  fpscr     │                0 │                    0 │                                                                0
  msp       │         20036b44 │            537094980 │                                   100000000000110110101101000100
  psp       │                0 │                    0 │                                                                0
  primask   │                0 │                    0 │                                                                0
  basepri   │               f0 │                  240 │                                                         11110000
  faultmask │                0 │                    0 │                                                                0
  control   │                4 │                    4 │                                                              100
  s0        │                0 │                    0 │                                                                0
  ...       │              ... │                  ... │                                                              ...
  s31       │         ffffffff │           4294967295 │                                 11111111111111111111111111111111
            ╵                  ╵                      ╵
```


### px4_interrupts

```
px4_interrupts
```

Pretty prints a table of all non-empty NuttX interrupts showing their state
(E=enabled, P=pending, A=active), priority, function pointer, name, and
argument.

```
(gdb) px4_interrupts
      ╷     ╷      ╷           ╷                             ╷
  IRQ │ EPA │ Prio │ Address   │ Function                    │ Argument
 ═════╪═════╪══════╪═══════════╪═════════════════════════════╪══════════════════════════════
  -13 │ e   │ -1   │ 0x8009914 │ arm_hardfault               │ 0x0
   -5 │     │ 0    │ 0x8009a08 │ arm_svcall                  │ 0x0
   -1 │     │ 80   │ 0x8013c40 │ stm32_timerisr              │ 0x0
    8 │ ep  │ 80   │ 0x8175054 │ stm32_exti2_isr             │ 0x0
   11 │ ep  │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x20020740 <g_dma>
   12 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x20020758 <g_dma+24>
   13 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x20020770 <g_dma+48>
   14 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x20020788 <g_dma+72>
   15 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x200207a0 <g_dma+96>
   16 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x200207b8 <g_dma+120>
   17 │ e   │ 80   │ 0x800949c │ stm32_dmainterrupt          │ 0x200207d0 <g_dma+144>
   19 │ e   │ 80   │ 0x8132bb8 │ can1_irq(int, void*, void*) │ 0x0
   20 │ e   │ 80   │ 0x8132bb8 │ can1_irq(int, void*, void*) │ 0x0
   21 │ e   │ 80   │ 0x8132bb8 │ can1_irq(int, void*, void*) │ 0x0
   23 │ e a │ 80   │ 0x8175104 │ stm32_exti95_isr            │ 0x0
      ╵     ╵      ╵           ╵                             ╵
```


### px4_gpios

```
px4_gpios [-f FILTER] [-ff FUNCTION_FILTER] [-pf PIN_FILTER]
          [-s {pin,config,i,o,af,name,function}] [-c COLUMNS]

options:
  -f, --filter FILTER
                        Regex filter for FMU names.
  -ff, --function-filter FUNCTION_FILTER
                        Regex filter for FMU functions.
  -pf, --pin-filter PIN_FILTER
                        Regex filter for GPIO pin names.
  -s, --sort {pin,config,i,o,af,name,function}
                        Column name to sort the table by.
  -c, --columns COLUMNS
                        Number of columns to print.
```

Reads the GPIO peripheral space and prints a table of the individual pin
configuration, input/output state and alternate function. If a pinout is
provided, the pins will be matched with their names and functions.

- Config: Condensed view with omitted defaults.  
    MODER:  IN=Input, OUT=Output, ALT=Alternate Function, AN=Analog,  
    OTYPER: +OD=OpenDrain, (PushPull omitted),  
    PUPDR:  +PU=PullUp, +PD=PullDown, (Floating omitted),  
    SPEEDR: +M=Medium, +H=High, +VH=Very High, (Low omitted).  
    LOCKR: +L=Locked, (Unlocked omitted).

- Input (IDR), Output (ODR): _=Low, ^=High  
    Input only shown for IN, OUT, and ALT.  
    Output only shown for OUT.

- Alternate Function (AFR): only shown when config is ALT.  
    Consult the datasheet for device-specific mapping.

```
(gdb) px4_gpios -c 1
      ╷           ╷   ╷   ╷    ╷                 ╷
  Pin │ Config    │ I │ O │ AF │ Name            │ Function
 ═════╪═══════════╪═══╪═══╪════╪═════════════════╪═══════════════════════════════════════
  A0  │ AN        │   │   │    │ ADC1_IN0        │ SCALED_VDD_3V3_SENSORS1
  A1  │ ALT+VH    │ ^ │   │ 11 │ ETH_REF_CLK     │ ETH_REF_CLK
  A2  │ ALT+VH    │ ^ │   │ 11 │ ETH_MDIO        │ ETH_MDIO
  A3  │ IN        │ ^ │   │    │ USART2_RX       │ USART2_RX_TELEM3
  A4  │ AN        │   │   │    │ ADC1_IN4        │ SCALED_VDD_3V3_SENSORS2
  A5  │ ALT+H     │ ^ │   │  5 │ SPI1_SCK        │ SPI1_SCK_SENSOR1_ICM20602
  A6  │ IN        │ _ │   │    │ SPI6_MISO       │ SPI6_MISO_EXTERNAL1
  A7  │ ALT+VH    │ _ │   │ 11 │ ETH_CRS_DV      │ ETH_CRS_DV
  A8  │ ALT+H     │ _ │   │  1 │ TIM1_CH1        │ FMU_CH4
  A9  │ IN+PD     │ _ │   │    │ USB_OTG_FS_VBUS │ VBUS_SENSE
  A10 │ ALT+H     │ ^ │   │  1 │ TIM1_CH3        │ FMU_CH2
  A11 │ ALT+VH    │ _ │   │ 10 │ USB_OTG_FS_DM   │ USB_D_N
  A12 │ ALT+VH    │ _ │   │ 10 │ USB_OTG_FS_DP   │ USB_D_P
  A13 │ ALT+PU+VH │ _ │   │  0 │ SWDIO           │ FMU_SWDIO
  A14 │ ALT+PD    │ _ │   │  0 │ SWCLK           │ FMU_SWCLK
  A15 │ OUT       │ ^ │ ^ │    │                 │ SPI6_nCS2_EXTERNAL1
  B0  │ AN        │   │   │    │ ADC1_IN8        │ SCALED_VDD_3V3_SENSORS3
  B1  │ AN        │   │   │    │ ADC1_IN9        │ SCALED_V5
  B2  │ ALT+H     │ _ │   │  7 │ SPI3_MOSI       │ SPI3_MOSI_SENSOR3_BMI088
```

You can also regex filter and sort pin names:

```
(gdb) px4_gpios -ff US?ART -s name
      ╷           ╷   ╷   ╷    ╷            ╷
  Pin │ Config    │ I │ O │ AF │ Name       │ Function
 ═════╪═══════════╪═══╪═══╪════╪════════════╪═════════════════════════════
  H14 │ IN        │ ^ │   │    │ UART4_RX   │ UART4_RX
  H13 │ IN        │ _ │   │    │ UART4_TX   │ UART4_TX
  C9  │ ALT       │ _ │   │  7 │ UART5_CTS  │ UART5_CTS_TELEM2
  C8  │ OUT       │ _ │ _ │    │ UART5_RTS  │ UART5_RTS_TELEM2
  D2  │ ALT+PU+VH │ ^ │   │  8 │ UART5_RX   │ UART5_RX_TELEM2
  B9  │ ALT+PU+VH │ ^ │   │  7 │ UART5_TX   │ UART5_TX_TELEM2
  E10 │ ALT       │ ^ │   │  8 │ UART7_CTS  │ UART7_CTS_TELEM1
  E9  │ OUT       │ _ │ _ │    │ UART7_RTS  │ UART7_RTS_TELEM1
  F6  │ ALT+PU+VH │ ^ │   │  8 │ UART7_RX   │ UART7_RX_TELEM1
  E8  │ ALT+PU+VH │ ^ │   │  8 │ UART7_TX   │ UART7_TX_TELEM1
  E0  │ IN        │ ^ │   │    │ UART8_RX   │ UART8_RX_GPS2
  E1  │ IN        │ ^ │   │    │ UART8_TX   │ UART8_TX_GPS2
  B15 │ ALT+PU+VH │ ^ │   │  4 │ USART1_RX  │ USART1_RX_GPS1
  B14 │ ALT+PU+VH │ ^ │   │  4 │ USART1_TX  │ USART1_TX_GPS1
  D3  │ IN        │ ^ │   │    │ USART2_CTS │ USART2_CTS_TELEM3
  D4  │ IN        │ ^ │   │    │ USART2_RTS │ USART2_RTS_TELEM3
  A3  │ IN        │ ^ │   │    │ USART2_RX  │ USART2_RX_TELEM3
  D5  │ IN        │ ^ │   │    │ USART2_TX  │ USART2_TX_TELEM3
  D9  │ ALT+PU+VH │ ^ │   │  7 │ USART3_RX  │ USART3_RX_DEBUG
  D8  │ ALT+PU+VH │ ^ │   │  7 │ USART3_TX  │ USART3_TX_DEBUG
  C7  │ ALT+PU+VH │ ^ │   │  8 │ USART6_RX  │ USART6_RX_FROM_IO__RC_INPUT
  C6  │ ALT+PU+VH │ ^ │   │  8 │ USART6_TX  │ USART6_TX_TO_IO__NC
      ╵           ╵   ╵   ╵    ╵            ╵
```

### px4_backtrace

Prints a backtrace using Python to show absolute file path names without
resolving function arguments, which can otherwise cause GDB to segfault.

```
(gdb) px4_backtrace
#0  0x081671ea in perf_set_elapsed(perf_counter_t, int64_t) at /PX4-Autopilot/src/lib/perf/perf_counter.cpp:286
#1  0x0812e62e in MixingOutput::updateLatencyPerfCounter(actuator_outputs_s const&) at /PX4-Autopilot/src/lib/mixer_module/mixer_module.cpp:1098
#2  0x0812eb92 in MixingOutput::updateStaticMixer() at /PX4-Autopilot/src/lib/mixer_module/mixer_module.cpp:748
#3  0x0812ebcc in MixingOutput::updateStaticMixer() at /PX4-Autopilot/src/lib/mixer_module/mixer_module.cpp:648
#4  0x08059dea in PX4IO::Run() at /PX4-Autopilot/src/drivers/px4io/px4io.cpp:541
#5  0x08059dea in PX4IO::Run() at /PX4-Autopilot/src/drivers/px4io/px4io.cpp:519
#6  0x081717fc in px4::WorkQueue::Run() at /PX4-Autopilot/platforms/common/px4_work_queue/WorkQueue.cpp:187
#7  0x08171938 in px4::WorkQueueRunner(void*) at /PX4-Autopilot/platforms/common/px4_work_queue/WorkQueueManager.cpp:236
#8  0x08014904 in pthread_startup() at /PX4-Autopilot/platforms/nuttx/NuttX/nuttx/libs/libc/pthread/pthread_create.c:59
```


### px4_rbreak

```
px4_rbreak (file):function:+offset | (file):function:regex
```

Finds the absolute location of a relative line number offset or regex pattern
inside a function inside an optional file name, then sets a breakpoint on that
location. This allows you to reliably set breakpoints inside files whose line
numbering and content is changing during development. Remember to escape all
special regex characters for the match to work correctly!

```
(gdb) px4_rbreak :nxsem_boostholderprio:nxsched_set_priority\(htcb, *rtcb->sched_priority\);
Breakpoint 1 at 0x800b5c0: file semaphore/sem_holder.c, line 380.
(gdb) px4_rbreak sem_holder.c:nxsem_restoreholderprio:+20
Breakpoint 2 at 0x800b620: file semaphore/sem_holder.c, line 550.
```


### px4_coredump

```
px4_coredump [--memory start:size] [--file coredump_{datetime}.txt] [--flash]
```

Dumps the memories into a coredump file suffixed with the current date and time.
The coredump file can be passed to the [CrashDebug](crashdebug.md) debug
backend. By default, the SRAM memories and all peripherals listed in the SVD
file of the target are copied. Optionally, the non-volatile FLASH memory can
also be dumped for later analysis.

```
(gdb) px4_coredump
Starting coredump...
Coredump completed in 4.5s
```

### px4_pshow

```
px4_pshow PERIPHERAL [REGISTER]
```

Visualize the bit fields of one or all registers of a peripheral using the
[`arm-gdb`](https://pypi.org/project/arm-gdb) plugin. This requires the
CMSIS-SVD file of the device, which is defaulted for FMUv5x/v6x. For other
devices, GDB must be launched with the correct `--svd` command line option.

Note that this command loads the SVD using `arm loadfile st SVDFILE` and then
acts as an alias for `arm inspect /hab st PERIPHERAL [REGISTER]`.

```
(gdb) px4_pshow DMA1 S7CR
DMA1.S7CR                        = 00001000000000010000010001010100                   // stream x configuration register
    EN                             ...............................0 - 0               // Stream enable / flag stream ready when read low
    DMEIE                          ..............................0. - 0               // Direct mode error interrupt enable
    TEIE                           .............................1.. - 1               // Transfer error interrupt enable
    HTIE                           ............................0... - 0               // Half transfer interrupt enable
    TCIE                           ...........................1.... - 1               // Transfer complete interrupt enable
    PFCTRL                         ..........................0..... - 0               // Peripheral flow controller
    DIR                            ........................01...... - 1               // Data transfer direction
    CIRC                           .......................0........ - 0               // Circular mode
    PINC                           ......................0......... - 0               // Peripheral increment mode
    MINC                           .....................1.......... - 1               // Memory increment mode
    PSIZE                          ...................00........... - 0               // Peripheral data size
    MSIZE                          .................00............. - 0               // Memory data size
    PINCOS                         ................0............... - 0               // Peripheral increment offset size
    PL                             ..............01................ - 1               // Priority level
    DBM                            .............0.................. - 0               // Double buffer mode
    CT                             ............0................... - 0               // Current target (only in double buffer mode)
    ACK                            ...........0.................... - 0               // ACK
    PBURST                         .........00..................... - 0               // Peripheral burst transfer configuration
    MBURST                         .......00....................... - 0               // Memory burst transfer configuration
    CHSEL                          ...0100......................... - 4               // Channel selection
```

### px4_pwatch

```
px4_pwatch [options] [PERIPHERAL | PERIPHERAL.REGISTER]+

options:
  --add, -a           Add these peripherals.
  --remove, -r        Remove these peripherals.
  --reset, -R         Reset watcher to peripheral reset values.
  --quiet, -q         Stop automatically reporting.
  --loud, -l          Automatically report on GDB stop event.
  --all, -x           Show all logged changes.
  --watch-write, -ww  Add a write watchpoint on registers.
  --watch-read, -wr   Add a read watchpoint on registers.
```

Visualize the differences in peripheral registers on every GDB stop event. You
can combine this with a GDB watchpoint to watch for changes in a peripheral
register file.

Add all peripheral registers to the watchlist: `px4_pwatch -a PER`.

Add a single peripheral register to the watchlist: `px4_pwatch -a PER.REG`.

Remove all peripheral registers from the watchlist: `px4_pwatch -r PER`.

Remove a single peripheral register: `px4_pwatch -r PER.REG` or `px4_pwatch -r` for all.

Disable automatic reporting: `px4_pwatch -q`.

Enable automatic reporting: `px4_pwatch -l`.

Fetch last difference report: `px4_pwatch PER` or `px4_pwatch` for all.

Reset peripheral values: `px4_pwatch -R PER` or `px4_pwatch -R` for all.

Hint: You can specify multiple peripheral and register names per command.  

```
(gdb) px4_pwatch --loud --add DMA1 DMA2.S0CR UART4.CR1 I2C2
(gdb) continue
Continuing.
^C
Program received signal SIGINT, Interrupt.
nx_start () at init/nx_start.c:805
805       for (; ; )
Differences for DMA1:
- DMA1.LISR                        = 00000000000000000000110000000000                   // low interrupt status register
-     HTIF1                          .....................1.......... - 1               // Stream x half transfer interrupt flag (x=3..0)
-     TCIF1                          ....................1........... - 1               // Stream x transfer complete interrupt flag (x = 3..0)
+ DMA1.LISR                        = 00000000000000000000000000000000                   // low interrupt status register
+     HTIF1                          .....................0.......... - 0               // Stream x half transfer interrupt flag (x=3..0)
+     TCIF1                          ....................0........... - 0               // Stream x transfer complete interrupt flag (x = 3..0)
- DMA1.HISR                        = 00000000000000000000000000110001                   // high interrupt status register
-     FEIF4                          ...............................1 - 1               // Stream x FIFO error interrupt flag (x=7..4)
-     HTIF4                          ...........................1.... - 1               // Stream x half transfer interrupt flag (x=7..4)
-     TCIF4                          ..........................1..... - 1               // Stream x transfer complete interrupt flag (x=7..4)
+ DMA1.HISR                        = 00000000000000000000000000000000                   // high interrupt status register
+     FEIF4                          ...............................0 - 0               // Stream x FIFO error interrupt flag (x=7..4)
+     HTIF4                          ...........................0.... - 0               // Stream x half transfer interrupt flag (x=7..4)
+     TCIF4                          ..........................0..... - 0               // Stream x transfer complete interrupt flag (x=7..4)
```

Attach a write watchpoint to a register range: `px4_pwatch -a -ww PER.REG`.  
Other watchpoints: write=`-ww`, read=`-wr`, and write+read=`-ww -wr`.

```
(gdb) px4_pwatch --add --loud --watch-write DMA1
watch *(uint8_t[256]*)0x40026000
Hardware watchpoint 1: *(uint8_t[256]*)0x40026000
(gdb) continue
Continuing.
Program received signal SIGTRAP, Trace/breakpoint trap.
stm32_dmasetup (handle=0x20020770 <g_dma+48>, paddr=1073757196, maddr=<optimized out>, ntransfers=ntransfers@entry=18, scr=1024) at chip/stm32_dma.c:696
696       dmast_putreg(dmast, STM32_DMA_SNDTR_OFFSET, ntransfers);
Differences for DMA1:
- DMA1.S2PAR                       = 00000000000000000000000000000000                   // stream x peripheral address register
-     PA                             00000000000000000000000000000000 - 00000000        // Peripheral address
+ DMA1.S2PAR                       = 01000000000000000011110000001100                   // stream x peripheral address register
+     PA                             01000000000000000011110000001100 - 40003c0c        // Peripheral address
- DMA1.S2M0AR                      = 00000000000000000000000000000000                   // stream x memory 0 address register
-     M0A                            00000000000000000000000000000000 - 00000000        // Memory 0 address
+ DMA1.S2M0AR                      = 00100000000000110000000111100000                   // stream x memory 0 address register
+     M0A                            00100000000000110000000111100000 - 200301e0        // Memory 0 address
```


## Debugging HardFaults

When attaching GDB to your target, it enables exception vector catching so that
any fault triggers a breakpoint *before* the NuttX hardfault handler takes over.
This allows you to perform a backtrace and see the problematic location
immediately instead of using the hardfault log (see `emdbg.debug.crashdebug`):

```
Program received signal SIGTRAP, Trace/breakpoint trap.
exception_common () at armv7-m/arm_exception.S:144
144             mrs             r0, ipsr                                /* R0=exception number */
(gdb) bt
#0  exception_common () at armv7-m/arm_exception.S:144
#1  <signal handler called>
#2  inode_insert (parent=0x0, peer=0x0, node=0x2007c010) at inode/fs_inodereserve.c:117
#3  inode_reserve (path=path@entry=0x81895f4 "/dev/console", mode=mode@entry=438, inode=inode@entry=0x20036bac) at inode/fs_inodereserve.c:222
#4  0x0800ac90 in register_driver (path=path@entry=0x81895f4 "/dev/console", fops=fops@entry=0x8189968 <g_serialops>, mode=mode@entry=438, priv=priv@entry=0x20020570 <g_usart3priv>) at driver/fs_registerdriver.c:78
#5  0x0800a6f2 in uart_register (path=path@entry=0x81895f4 "/dev/console", dev=dev@entry=0x20020570 <g_usart3priv>) at serial/serial.c:1743
#6  0x080093a6 in arm_serialinit () at chip/stm32_serial.c:3660
#7  0x08014554 in up_initialize () at common/arm_initialize.c:122
#8  0x0800b122 in nx_start () at init/nx_start.c:656
#9  0x080082be in __start () at chip/stm32_start.c:273
#10 0x08000306 in ?? ()
Backtrace stopped: previous frame identical to this frame (corrupt stack?)
```

To understand what exactly triggered the hardfault, you can use the `arm scb /h`
command to display the fault registers:

```
(gdb) arm scb /h
CPUID                            = 411fc270                   // CPUID Base Register
    Variant                        ..1..... - Revision: r1pX
    Architecture                   ...f.... - ARMv7-M
    PartNo                         ....c27. - Cortex-M7
    Revision                       .......0 - Patch: rXp0
CFSR                             = 00008200                   // Configurable Fault Status Register
    MMFSR                          ......00 - 00              // MemManage Fault Status Register
    BFSR                           ....82.. - 82              // BusFault Status Register
    BFARVALID                      ....8... - 1               // Indicates if BFAR has valid contents.
    PRECISERR                      .....2.. - 1               // Indicates if a precise data access error has occurred, and the processor has written the faulting address to the BFAR.
    UFSR                           0000.... - 0000            // UsageFault Status Register
HFSR                             = 40000000                   // HardFault Status Register
    FORCED                         4....... - 1               // Indicates that a fault with configurable priority has been escalated to a HardFault exception.
DFSR                             = 00000008                   // Debug Fault Status Register
    VCATCH                         .......8 - Vector catch triggered // Indicates triggering of a Vector catch
MMFAR                            = 00000008                   // MemManage Fault Address Register
BFAR                             = 00000008                   // BusFault Address Register
AFSR                             = 00000000                   // Auxiliary Fault Status Register
```

In this example, a precise bus fault occurred when accessing address 8. Since
the bus fault is precise, we can walk up the stack frames to the exact offending
instruction:

```
(gdb) frame 2
#2  inode_insert (parent=0x0, peer=0x0, node=0x2007c010) at inode/fs_inodereserve.c:117
117           node->i_peer    = parent->i_child;
```

In this example, the `parent` pointer is zero, which attempts to perform a read
at offset 8, which corresponds to `offsetof(parent, i_child)`:

```
(gdb) p &((struct inode *)0)->i_child
$1 = (struct inode **) 0x8
```


[gdbgui]: https://www.gdbgui.com
[xpack]: https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/tag/v12.2.1-1.2
[gdbpy]: https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html
