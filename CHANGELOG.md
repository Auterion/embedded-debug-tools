# Changelog

## 1.1.1

- Better visualization of the number of backtraces in callgraphs.
- Load NuttX RTOS plugin from PX4 into JLink if available.
- More opportunistic backtrace information printing.

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
