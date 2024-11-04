# Analyze inline function usage

Function inlining generally is a space-time tradeoff where more inlining helps with execution speed but
increases FLASH usage. This tool helps to see which functions are inlined where and how much FLASH usage
this inlining causes.

## Command Line Interface

You can analyze the inline usage like this:

```sh
python3 -m emdbg.analyze.inline -f test.elf
```

The analysis can take some time as it has to traverse all DIEs of the DWARF data.