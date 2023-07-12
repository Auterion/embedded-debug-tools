# Visualize Backtraces

You can generate backtraces using the GDB `px4_backtrace` command.
To generate a log of backtrace, use the `px4_breaktrace {func}` command via the
commands defined by the `emdbg.bench.skynode` module.


## Command Line Interface

You can convert calltraces into SVG call graphs like this:

```sh
python3 -m emdbg.analyze.callgraph calltrace_log.txt --svg --type FileSystem
```

You can change the type to use a specific peripheral if you traced access to
that peripheral.

## Installation

You need to install graphviz for the analysis functionality:

```sh
# Ubuntu
sudo apt install graphviz
# macOS
brew install graphviz
```
