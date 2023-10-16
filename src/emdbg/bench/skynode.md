# Auterion Skynode Test Bench

The test bench consists of a Auterion Skynode FMU that is powered through a
Yocto Relay and connected to a J-Link, USB-Serial adapter for the NSH and a
Digilent Analog Discovery 2.

The main entry point is the `emdbg.bench.skynode()` function, which
orchestrates the entire setup and yields an initialized bench object.


## Command Line Interface

To quickly debug something interactively on the test bench, you can launch GDB
directly:

```sh
python3 -m emdbg.bench.skynode --px4-dir path/to/PX4-Autopilot \
	--target px4_fmu-v5x -ui tui --stlink
```
