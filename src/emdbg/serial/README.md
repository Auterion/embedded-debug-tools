# Serial Connection Management

The PX4 NSH can be accessed via a context manager.
The received stream is polled in a background thread, so that no data is lost.
See the `emdbg.serial.protocol.Nsh` class for all functionality.

```py
with emdbg.serial.nsh(serial) as nsh:
	# Log all received data to file
	nsh.log_to_file("path/to/log.txt")

	# Send a command and wait for response
	response = nsh.command("top once")

	# Disable logging and close log file
	nsh.log_to_file(None)
```
