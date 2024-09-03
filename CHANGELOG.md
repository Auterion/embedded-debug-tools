# Changelog

## 1.5.5

- Fix NSH protocol `wait_for()` function implementation.

## 1.5.4

- Allow NSH port to be opened by filepath.

## 1.5.3

- Fix enabling vector catch with OpenOCD.
- Substitute GitHub CI path with local path by default.
- Show stack overflow warning if stack usage >90%.
- Do not attempt to load SVD file if target is unknown.
- Fix UartBuffer pointer address computation.

## 1.5.2

- Add erase command to JLink backend.
- Fix px4_dmesg command.

## 1.5.1

- Fix NSH protocol closing port when device is not ready for reading.
- Fix wrapping memory read for buffers.
- Use up-to-date OpenOCD for uploading firmware instead of GDB.

## 1.5.0

- Add serial number support for selecting J-Link and Openocd debug probes.

## 1.4.1

- Fix error handling in `find_serial_port`.
- Fix ignoring commands argument in openocd `call()`.

## 1.4.0

- Return string from Nsh protocol instead of list of lines.
- Mark `px4_perf` counters changed since last GDB interrupt.

## 1.3.11

- Add `px4_perf` command to list performance counters.

## 1.3.10

- Add `px4_dmesg` command and pretty printer to display the dmesg buffer in GDB.
- Add missing SDMMC2 peripheral to STM32F765 SVD file.
- Add CrashDebug to `killme` command.
- Limit yoctopuce dependency to v1.0.

## 1.3.9

- Fix recognition of PX4 hardfault logs as crashdumps.

## 1.3.8

- Fix NuttX semaphore patch formatting.
- Allow tracing to be started with a J-Link too.
- Fix Orbtrace FMU config.
- Fix site-package paths on Linux.
- Add `killme` command for ending a misbehaving GDB session by force.

## 1.3.7

- Add missing NuttX Semaphore tracing patches.
- Test all patches first to prevent partial patch application.
- Split ITM tracing patch to work with NuttX v10 and v11.

## 1.3.6

- Update SVD file for FMUv6x.

## 1.3.5

- Search for bootloader ELF file and add as symbol file.
- Reset device using RESET pin on J-Link.
- Fix missing speed argument when using J-Link command line.

## 1.3.4

- Update SVD files for FMUv5x and FMUv6x.

## 1.3.3

- Simplify macOS installation instructions.
- Add `uart_buffer_s` pretty printer.
- Set MSP in addition to SP to get proper task switches also on OpenOCD.
- Fix semaphore pretty printer: 0 also means taken, not available.

## 1.3.2

- Improve installation guides for GDB and CrashDebug.
- Create a new `trace.swo` file when using OpenOCD instead of appending.
- Fix broken ITM tracing macro.

## 1.3.1

- Highlight priority boosts in `px4_tasks` command.
- Fix `px4_tasks` and `px4_files` rendering when no tasks are present.
- Fix `px4_gpio` default sort key indexing.

## 1.3.0

- Add px4_files command for showing open files.
- Use rich for displaying tables.
- Save device identifier memories in coredump.
- Add a pretty-printer for NuttX semaphores.
- Fix `gdb_getfield()` function to return the value and not the field.
- Add optionally reading FLASH when coredumping.
- Fix `px4.Base.read_string()` function when length is unknown.
- Search for ELF file in bench target folder.
- Fix accessing open files of tasks.
- Add support for ORBTrace mini debug probe.

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
