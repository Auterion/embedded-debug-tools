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

```sh
sudo mkdir -p /opt/xpack
curl -L https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v12.2.1-1.2/xpack-arm-none-eabi-gcc-12.2.1-1.2-linux-x64.tar.gz | \
        sudo tar -xvzf - -C /opt/xpack/
# Only link the -py3 into your path
sudo ln -s /opt/xpack/xpack-arm-none-eabi-gcc-12.2.1-1.2/bin/arm-none-eabi-gdb-py3 \
        /opt/gcc-arm-none-eabi-9-2020-q2-update/bin
```

On macOS you additionally need to clear the quarantine flags after expansion:

```sh
sudo mkdir -p /opt/xpack

# x86_64 binary
curl -L https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v12.2.1-1.2/xpack-arm-none-eabi-gcc-12.2.1-1.2-darwin-x64.tar.gz | \
        sudo tar -xvzf - -C /opt/xpack/
# ARM64 binary
curl -L https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/download/v12.2.1-1.2/xpack-arm-none-eabi-gcc-12.2.1-1.2-darwin-arm64.tar.gz | \
        sudo tar -xvzf - -C /opt/xpack/

# Clear the quarantine flag
sudo xattr -r -d com.apple.quarantine /opt/xpack/

# Only link the -py3 into your path
sudo ln -s /opt/xpack/xpack-arm-none-eabi-gcc-12.2.1-1.2/bin/arm-none-eabi-gdb-py3 \
        /usr/local/bin
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
Device(armv7e-m, 0x411fc271, 0x450, 0x2003 -> STM32H742, STM32H743/753, STM32H750 at revision Y)
SCB registers:
CPUID                            = 411fc271
    Variant                        ..1..... - Revision: r1pX
    Architecture                   ...f.... - ARMv7-M
    PartNo                         ....c27. - Cortex-M7
    Revision                       .......1 - Patch: rXp1
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
       TCB  PID NAME                   LOCATION         CPU(ms) CPU(%)  USED/STACK  PRIO(BASE)  FDs  STATE  WAITING FOR
0x20028164    0 Idle Task              nx_start            8873   30.5   354/  726     0(   0)    3  RUN
0x2007c2d0    1 hpwork                 nxsig_timedwait        0    0.0   332/ 1264   249( 249)    3  w:sig  signal
0x2007ce80    2 lpwork                 nxsig_timedwait        0    0.0   588/ 1616    50(  50)    3  w:sig  signal
0x2007db90    3 init                   nxsem_wait             0    0.0  2348/ 3080   100( 100)    3  w:sem  0x2007dbe0 <g_usart3priv + 36>
0x2007f3e0    4 wq:manager             nxsem_wait             0    0.0   452/ 1256   255( 255)    5  w:sem  0x2007f430: 22x wq:manager
0x20003cd0   63 wq:hp_default          nxsem_wait           132    4.1  1132/ 1904   237( 237)    5  w:sem  0x20003d20
0x200045f0   77 wq:I2C3                nxsem_wait            30    0.9   724/ 2336   244( 244)    5  w:sem  0x20004640
0x200025f0  613 dataman                nxsem_wait             0    0.0   860/ 1208    90(  90)    4  w:sem  0x20002640 <g_work_queued_sema>
0x200021b0  615 wq:lp_default          nxsem_wait             5    0.2  1004/ 1920   205( 205)    5  w:sem  0x20002200
0x200039b0  634 wq:uavcan              nxsem_wait            52    1.5  1692/ 3624   236( 236)    5  w:sem  0x20003a00
0x20005410  699 wq:SPI3                nxsem_wait           246    7.2  1336/ 2336   251( 251)    5  w:sem  0x20005460
0x2000dd40  710 wq:SPI2                nxsem_wait           174    5.1  1812/ 2336   252( 252)    5  w:sem  0x2000dd90
0x2000ebd0  713 wq:SPI1                nxsem_wait           151    4.4  1724/ 2336   253( 253)    5  w:sem  0x2000ec20
0x2000fd30  718 wq:I2C4                nxsem_wait            13    0.4   912/ 2336   243( 243)    5  w:sem  0x2000fd80
0x20010ab0  747 wq:I2C1                nxsem_wait             3    0.1  1116/ 2336   246( 246)    5  w:sem  0x20010b00
0x20013890  754 wq:I2C2                nxsem_wait             9    0.3   792/ 2336   245( 245)    5  w:sem  0x200138e0
0x2000c2b0  830 wq:nav_and_controllers nxsem_wait           140    4.1  1276/ 2280   242( 242)    5  w:sem  0x2000c300
0x200163d0  840 wq:rate_ctrl           nxsem_wait           264    7.7  1492/ 3152   255( 255)    5  w:sem  0x20016420
0x20019050  842 wq:INS0                nxsem_wait           391   11.4  4252/ 6000   241( 241)    5  w:sem  0x200190a0
0x2001c260  847 commander              nxsig_timedwait       50    1.5  1244/ 3224   231( 231)    5  w:sig  signal
0x20038cf0  940 mavlink_if0            nxsig_timedwait      260    7.7  1916/ 2736   101( 101)    4  w:sig  signal
0x2003bfb0  944 mavlink_rcv_if0        nxsem_wait            19    0.7  1756/ 5064   175( 175)    4  w:sem  0x2003c000
0x200321b0 1113 gps                    nxsem_wait             2    0.1  1204/ 1912   205( 205)    4  w:sem  0x20032200
0x20036230 1297 mavlink_if1            nxsig_timedwait       88    2.5  1908/ 2736   101( 101)    4  w:sig  signal
0x20042390 1299 mavlink_rcv_if1        nxsem_wait            13    0.4  1300/ 5064   175( 175)    4  w:sem  0x200423e0
0x2003d5e0 1372 mavlink_if2            nxsig_timedwait      162    4.7  1916/ 2744   101( 101)    4  w:sig  signal
0x20046f50 1373 mavlink_rcv_if2        nxsem_wait            15    0.5  1300/ 5064   175( 175)    4  w:sem  0x20046fa0
0x20012610 1399 navigator              nxsem_wait             4    0.1  1000/ 2072   105( 105)    6  w:sem  0x20012660
0x2003f1b0 1557 logger                 nxsem_wait            13    0.4  2556/ 3648   230( 230)    3  w:sem  0x2003f200
0x2004ff30 1592 log_writer_file        nxsem_wait             0    0.0   372/ 1176    60(  60)    3  w:sem  0x2004ff80

Processes: 30 total, 1 running, 29 sleeping
CPU usage: 66.0% tasks, 3.5% sched, 30.5% idle
Uptime: 16.91s total, 0.48s interval
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
px4_registers [COLUMNS=3]
```

Pretty prints a compact, multi-column table with all register values.

```
(gdb) px4_registers 2
r0                    0x2                    2      :      primask           0x0           0
r1             0x2003b15c            537112924      :      basepri          0x80         128
r2             0x2007dc1c            537386012      :      faultmask         0x0           0
r3             0x2002d0d8            537055448      :      control           0x4           4
r4             0x2003c3f0            537117680      :      s0                0x0           0
r5             0x2003b0d0            537112784      :      s1                0x0           0
r6                   0xf0                  240      :      s2                0x0           0
r7             0x2003b108            537112840      :      s3                0x0           0
r8             0x2003c3f0            537117680      :      s4                0x0           0
r9                    0x1                    1      :      s5                0x0           0
r10                   0xa                   10      :      s6                0x0           0
r11                   0x0                    0      :      s7                0x0           0
r12            0x2003c2d8            537117400      :      s8                0x0           0
sp             0x2003c3c8            537117640      :      s9                0x0           0
lr              0x800b3cf            134263759      :      s10               0x0           0
pc              0x8012b48            134294344      :      s11               0x0           0
xpsr           0x41000000           1090519040      :      s12               0x0           0
d0                    0x0                    0      :      s13        0x7ff80000  2146959360
d1                    0x0                    0      :      s14               0x0           0
d2                    0x0                    0      :      s15               0x0           0
d3                    0x0                    0      :      s16               0x0           0
d4                    0x0                    0      :      s17               0x0           0
d5                    0x0                    0      :      s18               0x0           0
d6     0x7ff8000000000000  9221120237041090560      :      s19               0x0           0
d7                    0x0                    0      :      s20               0x0           0
d8                    0x0                    0      :      s21               0x0           0
d9                    0x0                    0      :      s22               0x0           0
d10                   0x0                    0      :      s23               0x0           0
d11                   0x0                    0      :      s24               0x0           0
d12                   0x0                    0      :      s25               0x0           0
d13                   0x0                    0      :      s26               0x0           0
d14                   0x0                    0      :      s27               0x0           0
d15                   0x0                    0      :      s28               0x0           0
fpscr          0x30000001            805306369      :      s29               0x0           0
msp            0x20030e28            537071144      :      s30               0x0           0
psp                   0x0                    0      :      s31               0x0           0
```


### px4_interrupts

```
px4_interrupts [COLUMNS=1]
```

Pretty prints a table of all non-empty NuttX interrupts showing their state
(E=enabled, P=pending, A=active), priority (P), function pointer, name, and
argument.

```
(gdb) px4_interrupts
IRQ EPA P       ADDR =  FUNCTION                                        ARGUMENT
-13     8  0x800972c =  arm_hardfault
 -5 e   8  0x800981c =  arm_svcall
 -1 e   8  0x8011efc =  stm32_timerisr
  8     8  0x8167d40 =  stm32_exti2_isr
 11 e   8  0x800936c =  stm32_dmainterrupt                              0x20020740 <g_dma>
 12     8  0x800936c =  stm32_dmainterrupt                              0x20020758 <g_dma+24>
 13     8  0x800936c =  stm32_dmainterrupt                              0x20020770 <g_dma+48>
 14 e   8  0x800936c =  stm32_dmainterrupt                              0x20020788 <g_dma+72>
 15 e   8  0x800936c =  stm32_dmainterrupt                              0x200207a0 <g_dma+96>
 16 e   8  0x800936c =  stm32_dmainterrupt                              0x200207b8 <g_dma+120>
 17 e   8  0x800936c =  stm32_dmainterrupt                              0x200207d0 <g_dma+144>
 19     8  0x81300d8 =  can1_irq(int, void*, void*)
 20     8  0x81300d8 =  can1_irq(int, void*, void*)
 21 e   8  0x81300d8 =  can1_irq(int, void*, void*)
 23 e   8  0x8167df0 =  stm32_exti95_isr
 27 e   8  0x816b0f8 =  io_timer_handler0
 30 e   8  0x816b0f0 =  io_timer_handler1
 31 e   8  0x816826a =  stm32_i2c_isr                                   0x20020b44 <stm32_i2c1_priv>
 32     8  0x816826a =  stm32_i2c_isr                                   0x20020b44 <stm32_i2c1_priv>
 33     8  0x816826a =  stm32_i2c_isr                                   0x20020b78 <stm32_i2c2_priv>
 34     8  0x816826a =  stm32_i2c_isr                                   0x20020b78 <stm32_i2c2_priv>
 37 e   8  0x8008dd4 =  up_interrupt                                    0x200203a0 <g_usart1priv>
 39     8  0x8008dd4 =  up_interrupt                                    0x20020570 <g_usart3priv>
 40 e   8  0x8167df8 =  stm32_exti1510_isr
 43 e   8  0x816b0e8 =  io_timer_handler2
 46     8  0x816da88 =  hrt_tim_isr
 47 e   8  0x800936c =  stm32_dmainterrupt                              0x200207e8 <g_dma+168>
 52 e   8  0x8008dd4 =  up_interrupt                                    0x20020000 <g_uart4priv>
 53 e   8  0x8008dd4 =  up_interrupt                                    0x200200e8 <g_uart5priv>
 54 e   8  0x8130608 =  TIMX_IRQHandler(int, void*, void*)
 56 e   8  0x800936c =  stm32_dmainterrupt                              0x20020800 <g_dma+192>
 57 e   8  0x800936c =  stm32_dmainterrupt                              0x20020818 <g_dma+216>
 58     8  0x800936c =  stm32_dmainterrupt                              0x20020830 <g_dma+240>
 59   a 8  0x800936c =  stm32_dmainterrupt                              0x20020848 <g_dma+264>
 60     8  0x800936c =  stm32_dmainterrupt                              0x20020860 <g_dma+288>
 63     8  0x81300a4 =  can2_irq(int, void*, void*)
 64     8  0x81300a4 =  can2_irq(int, void*, void*)
 65  p  8  0x81300a4 =  can2_irq(int, void*, void*)
 67     8  0x80137e4 =  stm32_usbinterrupt
 68     8  0x800936c =  stm32_dmainterrupt                              0x20020878 <g_dma+312>
 69     8  0x800936c =  stm32_dmainterrupt                              0x20020890 <g_dma+336>
 70     8  0x800936c =  stm32_dmainterrupt                              0x200208a8 <g_dma+360>
 71     8  0x8129c30 =  ArchPX4IOSerial::_interrupt(int, void*, void*)  0x20006170
 72     8  0x816826a =  stm32_i2c_isr                                   0x20020bac <stm32_i2c3_priv>
 73     8  0x816826a =  stm32_i2c_isr                                   0x20020bac <stm32_i2c3_priv>
 82     8  0x8008dd4 =  up_interrupt                                    0x200201d0 <g_uart7priv>
 95     8  0x816826a =  stm32_i2c_isr                                   0x20020be0 <stm32_i2c4_priv>
 96     8  0x816826a =  stm32_i2c_isr                                   0x20020be0 <stm32_i2c4_priv>
103     8  0x816cf64 =  stm32_sdmmc_interrupt                           0x20020ef4 <g_sdmmcdev2>
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
    OTYPER: +OD=OpenDrain, (+PP=PushPull omitted),  
    PUPDR:  +PU=PullUp, +PD=PullDown, (+FL=Floating omitted),  
    SPEEDR: +M=Medium, +H=High, +VH=Very High, (+L=Low omitted).

- Input (IDR), Output (ODR): _=Low, ^=High  
    Input only shown for IN, OUT, and ALT.  
    Output only shown for OUT.

- Alternate Function (AFR): only shown when config is ALT.  
    Consult the datasheet for device-specific mapping.

```
(gdb) px4_gpios -c 1
PIN  CONFIG     I O  AF  NAME             FUNCTION
A0   AN                  ADC1_IN0         SCALED_VDD_3V3_SENSORS1
A1   IN         _        ETH_REF_CLK      ETH_REF_CLK
A2   IN         ^        ETH_MDIO         ETH_MDIO
A3   IN         _        USART2_RX        USART2_RX_TELEM3
A4   AN                  ADC1_IN4         SCALED_VDD_3V3_SENSORS2
A5   ALT+H      ^     0  SPI1_SCK         SPI1_SCK_SENSOR1_ICM20602
A6   IN         ^        SPI6_MISO        SPI6_MISO_EXTERNAL1
A7   IN         _        ETH_CRS_DV       ETH_CRS_DV
A8   IN+PU      ^        TIM1_CH1         FMU_CH4
A9   IN+PD      _        USB_OTG_FS_VBUS  VBUS_SENSE
A10  IN+PU      ^        TIM1_CH3         FMU_CH2
A11  ALT+VH     _     0  USB_OTG_FS_DM    USB_D_N
A12  ALT+VH     _     0  USB_OTG_FS_DP    USB_D_P
A13  ALT+PU+VH  _     5  SWDIO            FMU_SWDIO
A14  ALT+PD     ^     0  SWCLK            FMU_SWCLK
A15  OUT        ^ ^                       SPI6_nCS2_EXTERNAL1
B0   AN                  ADC1_IN8         SCALED_VDD_3V3_SENSORS3
B1   AN                  ADC1_IN9         SCALED_V5
B2   ALT+H      _     0  SPI3_MOSI        SPI3_MOSI_SENSOR3_BMI088
```

You can also regex filter and sort pin names:

```
(gdb) px4_gpios -ff US?ART -s name
PIN  CONFIG     I O  AF  NAME        FUNCTION
H14  ALT+PU+VH  ^     9  UART4_RX    UART4_RX
H13  ALT+PU+VH  ^     0  UART4_TX    UART4_TX
C9   ALT        _     0  UART5_CTS   UART5_CTS_TELEM2
C8   OUT        ^ ^      UART5_RTS   UART5_RTS_TELEM2
D2   ALT+PU+VH  ^     0  UART5_RX    UART5_RX_TELEM2
B9   ALT+PU+VH  ^     0  UART5_TX    UART5_TX_TELEM2
E10  ALT        _     0  UART7_CTS   UART7_CTS_TELEM1
E9   OUT        _ _      UART7_RTS   UART7_RTS_TELEM1
F6   ALT+PU+VH  ^     0  UART7_RX    UART7_RX_TELEM1
E8   ALT+PU+VH  ^     0  UART7_TX    UART7_TX_TELEM1
E0   IN         ^        UART8_RX    UART8_RX_GPS2
E1   IN         _        UART8_TX    UART8_TX_GPS2
B15  ALT+PU+VH  ^     4  USART1_RX   USART1_RX_GPS1
B14  ALT+PU+VH  ^     9  USART1_TX   USART1_TX_GPS1
D3   IN         ^        USART2_CTS  USART2_CTS_TELEM3
D4   IN         _        USART2_RTS  USART2_RTS_TELEM3
A3   IN         _        USART2_RX   USART2_RX_TELEM3
D5   IN         _        USART2_TX   USART2_TX_TELEM3
D9   ALT+PU+VH  ^     9  USART3_RX   USART3_RX_DEBUG
D8   ALT+PU+VH  ^     9  USART3_TX   USART3_TX_DEBUG
C7   ALT+PU+VH  ^     0  USART6_RX   USART6_RX_FROM_IO__RC_INPUT
C6   ALT+PU+VH  ^     0  USART6_TX   USART6_TX_TO_IO__NC
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
px4_coredump [--memory start:size] [--file coredump_{datetime}.txt]
```

Dumps the memories into a coredump file suffixed with the current date and time.
The coredump file can be passed to the [CrashDebug](crashdebug.md) debug
backend. By default, the SRAM memories and all peripherals listed in the SVD
file of the target are copied.

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
(gdb)
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
(gdb)
```


[gdbgui]: https://www.gdbgui.com
[xpack]: https://github.com/xpack-dev-tools/arm-none-eabi-gcc-xpack/releases/tag/v12.2.1-1.2
[gdbpy]: https://sourceware.org/gdb/onlinedocs/gdb/Python-API.html
