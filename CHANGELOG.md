# Changelog

## 1.2.1

- emdbg.bench.fmu can load coredump or PX4 hardfault files directly.
- emdbg.debug.gdb can load corefiles in ELF format directly.
- Improve the px4_discover user command to show UID, package, and flash size.
- Fix decoding of file names in px4_tasks command.
- Robustify the user commands when running on NuttX without PX4.
- Set SWD clock to 8MHz for the built-in OpenOCD config files.
- Merge itm_logging into nuttx_tracing_itm patch.
- Fix px4_gpios AFR and LOCKR register offsets.
- Fix paths in null malloc patch.

## 1.2.0

- Add support for loading PX4 hardfault logs into the crashdebug backend.
- Trap fault vectors while debugging to allow backtrace to work correctly.
- Fix incorrect sorting of tasks in `px4_tasks` command.
- Display interrupt frame correctly in `px4_backtrace` command.
- Output a warning when a stack overflow has been detected in `px4_tasks` command.
- Configure GDB to display absolute filenames and one line of disassembly.
- Show function and file line in callgraph to easier distinguish nodes.
- Add malloc fuzzer to find code without proper OOM handling.

## 1.1.1

- Better visualization of the number of backtraces in callgraphs.
- Load NuttX RTOS plugin from PX4 into JLink if available.
- More opportunistic backtrace information printing.
- Add blocking continue with timeout for GDB/MI wrapper.
- Prevent an exception if taking a coredump.

## 1.1.0

- Add ORBetto tool to convert ITM/DWT traces to perfetto.dev format.
- Add support for FMUv6x.
- Detect STM32F7 vs STM32H7 at runtime via DEVID.
- Use SVD files to generate coredump also from peripherals.
- Choose correct GDB config files for JLink and OpenOCD backend.
- More Python 3.8 compatibility fixes.
- Patches:
    - Add patch for un-inlining SDMMC register access in NuttX.
    - Add patch for instrumenting NuttX heap access.
- GDB plugins:
    - Show backtrace of GDB plugin exceptions.
    - Add `px4_discover` command to show device identity.
    - Add `px4_reload` command to dynamically reload the GDB plugins without
      quitting and restarting the GDB session.
    - Fix `px4_interrupt` command displaying an offset for the EPA P flags.
    - Add `px4_reset` command to reset the device independent of backend.

## 1.0.3

- Fix Python 3.8 compatiblity.
- Add this changelog.

## 1.0.2

- Added missing READMEs to the package data so that `pdoc emdbg` works correctly.

## 1.0.1

- Initial release.
