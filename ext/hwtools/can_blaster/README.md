# CAN Blaster

This firmware floods a CAN bus with (extended) messages at a configurable rate
based on a [NUCLEO-L432KC board](https://www.st.com/en/evaluation-tools/nucleo-l432kc.html)
with a [Adafruit CAN Pal](https://www.adafruit.com/product/5708).

The bus speed is hardcoded to 125kb/s but can be changed at compile time.

The message rate is defaulted to 1000 messages per second, but can be configured
by sending the messages per seconds in decimal to the serial port or the NUCLEO.
Setting 0 messages per second turns the sending off.

The message identifier and content is chosen randomly.


## Wiring

| NUCLEO-L432KC | CAN Pal |
|---------------|---------|
| GND           | GND     |
| 3V3           | VIN     |
| D2            | TX      |
| D10           | RX      |
