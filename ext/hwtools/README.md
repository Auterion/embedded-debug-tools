# Hardware Tools

This directory contains the firmware for simple hardware tools that are used to
debug PX4 FMUs and related hardware.

The firmware is written in C++23 using [modm.io](https://modm.io) which can
create very small binaries that run on any STM32.


## Building

Follow the [installation instructions](https://modm.io/guide/installation/) for
ARM Cortex-M devices. We recommend you use a virtual environment for the Python
tools:

```sh
cd embedded-debug-tools/
python3 -m venv .venv
source .venv/bin/activate
pip3 install modm
```

Then build the firmware like this:

```sh
cd ext/hwtools/can_blaster/
# First generate the actual library code
lbuild build
# Build the whole thing
scons
# Upload the firmware via STLink
scons program
```


## Usage

Some tools require communication via serial port to configure the firmware.
We recommend you use `picocom` for this:

```sh
picocom -b 115200 /dev/ttyACM0
```

You can exit `picocom` via `Ctrl-A X`.
