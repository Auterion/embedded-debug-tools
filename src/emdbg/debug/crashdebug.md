# CrashDebug Post-Mortem Analysis

[CrashDebug][] is a post-mortem debugging tool for Cortex-M microcontrollers.
You can create core dumps from GDB using the `px4_coredump` command (see
`emdbg.debug.gdb`).


## Installation

You need to have the [platform-specific `CrashDebug` binary][binary] available
in your path, alternatively you can specify the binary path in your environment:

```sh
export PX4_CRASHDEBUG_BINARY=path/to/CrashDebug
```

[crashdebug]: https://github.com/adamgreen/CrashDebug
[binary]: https://github.com/adamgreen/CrashDebug/tree/master/bins
