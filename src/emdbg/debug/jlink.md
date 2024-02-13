# J-Link Debug Probe

The [J-Link debug probe][jlink] is a closed-source, commercial hardware probe
which supports almost all Cortex-M devices.


## Command Line Interface

Common tasks are wrapped in a simple Python CLI. For more complex use-cases,
use the J-Link drivers directly.

Reset the device remotely:

```sh
python3 -m emdbg.debug.jlink -device STM32F765II reset
```

Run the JLinkGDBServer as a blocking process
```py
python3 -m emdbg.debug.jlink -device STM32F765II run
```

Upload firmware to a device:

```py
python3 -m emdbg.debug.jlink -device STM32F765II upload --source path/to/firmware.elf
python3 -m emdbg.debug.jlink -device STM32F765II upload --source path/to/firmware.bin --load-addr 0x08008000
```

Connect to RTT channel 0 for up- and downlink. Opens a telnet client that can be
terminated with Ctrl+D.

```py
python3 -m emdbg.debug.jlink -device STM32F765II rtt --channel 0
```

Output log output over ITM port 1 at 4MHz

```py
python3 -m emdbg.debug.jlink -device STM32F765II itm --channel 1 --baudrate 4000000
```

## Installation

You need to have the [J-Link drivers][drivers] installed for this module to work:

### Ubuntu

```sh
wget --post-data "accept_license_agreement=accepted" https://www.segger.com/downloads/jlink/JLink_Linux_x86_64.deb
sudo dpkg -i JLink_Linux_x86_64.deb
```

### macOS

```sh
brew install segger-jlink
```

[jlink]: https://www.segger.com/products/debug-probes/j-link/
[drivers]: https://www.segger.com/downloads/jlink/
