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

OpenOCD works with all STLink debug probes.


### Ubuntu

Ubuntu 22.04 only ships with OpenOCD v0.11, which is quite old, so you need to
manually install OpenOCD v0.12:

```sh
wget "https://github.com/rleh/openocd-build/releases/download/0.12.0%2Bdev-snapshot.20230509.1502/openocd-0.12.0.dev.snapshot.20230509.1502.amd64.deb"
sudo dpkg -i openocd-0.12.0.dev.snapshot.20230509.1502.amd64.deb
sudo apt install -f
```

You also need to update the udev rules:

```sh
sudo tee /etc/udev/rules.d/70-st-link.rules > /dev/null <<'EOF'
# ST-LINK V2
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3748", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
# ST-LINK V2.1
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374b", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3752", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
# ST-LINK V3
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374d", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374e", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="374f", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3753", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="3754", ENV{ID_MM_DEVICE_IGNORE}="1", MODE="666"
# ST-LINK Serial
SUBSYSTEM=="tty", ATTRS{idVendor}=="0483", MODE="0666", GROUP="dialout"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### macOS

```sh
brew install openocd
```

[openocd]: https://openocd.org
