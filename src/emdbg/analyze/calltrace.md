# Call Graph Generation using GDB

During manual debugging, some semi-automatic tracing and logging options can be
enabled without changing the binary.
Note that GDB needs to halt the target for a small time for every breakpoint,
therefore it will slow down the execution quite significantly.
**YOU MUST NOT USE THIS TOOL IN FLIGHT!**

Here is a simple way to generate call graphs of a point of interest:

```sh
# Sample all calls to I2C for ~3min, automatically generates a SVG.
python3 -m emdbg.analyze.calltrace -v \
        --px4-dir path/to/PX4-Autopilot --target px4_fmu-v5x --jlink \
        --sample 180 --ex "break stm32_i2c_transfer"
```

Note that you can specify multiple tracepoints that can either be break- or
watchpoints, and even contain conditions:

- `--ex "break function1" --ex "break function2"`: multiple breakpoints.
- `--ex "break function1 if variable >= 2"`: conditional breakpoint.
- `--ex "awatch variable"`: watchpoint for write and read access.
- `--ex "watch variable1" --ex "rwatch variable2"`: write and read watchpoints.
- `--ex "watch *(type*)0xdeadbeef"`: watchpoint on a cast memory location.

Note that GDB always reads the variable memory of a triggered watchpoint to
determine and display what changed. Therefore, if you want to trap access to an
entire peripheral, there will be *significant* side-effects from GDB reading
registers!


## Examples

### SDMMC Register Access

```sh
python3 -m emdbg.patch nuttx_sdmmc_reg_access --apply -v
make px4_fmu-v5x
python3 -m emdbg.analyze.calltrace -v --target px4_fmu-v5x --type FileSystem \
    --sample 180 --ex load --ex "mon reset halt" --ex px4_calltrace_sdmmc --stlink
# Get a coffee, this is gonna take a while, then check for a calltrace_*.svg file
```
