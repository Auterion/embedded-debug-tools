# Patch Management

Applies patches to a folder of files, by copying new files into the right
locations and applying diff patches to existing files.
Note that the patch application can be reverted without git support.


```py
patchset = emdbg.patch.nuttx_tracing_itm("path/to/PX4-Autopilot")
# apply the patch
patchset.do()
# remove the patch
patchset.undo()
```


## Command Line Interface

A minimal CLI provides access to integrate the functionality into shell scripts.

To apply a patch set:

```sh
python3 -m emdbg.patch --px4-dir path/to/PX4-Autopilot nuttx_tracing_itm --apply
```

To remove a patch set:

```sh
python3 -m emdbg.patch --px4-dir path/to/PX4-Autopilot nuttx_tracing_itm --restore
```

