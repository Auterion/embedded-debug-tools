# CAN Loopback

This firmware receives a CAN message and transmits it unmodified.
Based on a [NUCLEO-L432KC board](https://www.st.com/en/evaluation-tools/nucleo-l432kc.html)
with a [Adafruit CAN Pal](https://www.adafruit.com/product/5708).

The bus speed is hardcoded to 125kb/s but can be changed at compile time.


## Wiring

| NUCLEO-L432KC | CAN Pal |
|---------------|---------|
| GND           | GND     |
| 3V3           | VIN     |
| D2            | TX      |
| D10           | RX      |
