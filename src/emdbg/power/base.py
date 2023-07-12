# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import time
import logging
LOGGER = logging.getLogger("power")

class Base:
    """
    Interface to enable and disable a single power source.
    """
    def _on(self):
        raise NotImplementedError

    def _off(self):
        raise NotImplementedError

    def on(self, delay: float = 1):
        """Switch relay channel on and wait for `delay` seconds."""
        LOGGER.debug(f"On and wait {delay:.1f}s")
        self._on()
        time.sleep(delay)

    def off(self, delay: float = 1):
        """Switch relay channel off and wait for `delay` seconds."""
        LOGGER.debug(f"Off and wait {delay:.1f}s")
        self._off()
        time.sleep(delay)

    def cycle(self, delay_off: float = 1, delay_on: float = 1):
        """
        Switch relay channel off and wait for `delay_off` seconds, then
        switch relay channel on and wait for `delay_on` seconds.
        """
        self.off(delay_off)
        self.on(delay_on)
