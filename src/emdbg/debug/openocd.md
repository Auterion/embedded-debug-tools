# OpenOCD Debug Probe

Wraps [OpenOCD][] and issues the right command to program the target.

```sh
python3 -m emdbg.debug.openocd upload --source path/to/project.elf
```

You can also reset the target:

```sh
python3 -m emdbg.debug.openocd reset
```

You can specify the device using the `-f` configuration option (defaulted to
STM32F7):

```sh
python3 -m emdbg.debug.openocd -f target/stm32h7x.cfg reset
```

You can use a different OpenOCD binary by setting the `PX4_OPENOCD`
environment variable before calling this script. This can be useful when
using a custom OpenOCD build for specific targets.

```sh
export PX4_OPENOCD=/path/to/other/openocd
```

(\* *only ARM Cortex-M targets*)

## Installation

```sh
# Ubuntu
sudo apt install openocd
# macOS
brew install open-ocd
```

OpenOCD works with all STLink debug probes.

[openocd]: https://openocd.org
