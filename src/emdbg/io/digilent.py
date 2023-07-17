# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from pydwf import DwfLibrary
from pydwf.utilities import openDwfDevice
from contextlib import contextmanager
from functools import lru_cache
import enum
import logging

LOGGER = logging.getLogger("io:dwf")
_DWF = None

@contextmanager
def analog_discovery(identifier: str):
    """
    Starts the DWF library, opens and resets the device and yields it.

    :param identifier: serial number of the device to connect to.
    """
    global _DWF
    if _DWF is None:
        _DWF = DwfLibrary()
    with openDwfDevice(_DWF, serial_number_filter=identifier) as device:
        try:
            LOGGER.info("Starting...")
            device.reset()
            yield Digilent(device)
        finally:
            device.reset()
            LOGGER.debug("Stopping.")

# -----------------------------------------------------------------------------
class DigilentPin:
    """
    Describes a single pin of the Digilent device. Useful only for low-speed
    sampling or driving.
    """
    class Config(enum.Enum):
        """
        Specifies the hardware configuration of the pin.
        """
        Input = enum.auto()
        """Input state"""
        PushPull = enum.auto()
        """Output state with strong high and low driver"""
        OpenDrain = enum.auto()
        """Output state with only a strong low driver"""
        OpenSource = enum.auto()
        """Output state with only a strong high driver"""

    class Level(enum.IntEnum):
        """
        Logic level of the pin, for input and output.
        """
        Low = 0,
        High = 1

    def __init__(self, dio, mask: int):
        """
        :param dio: digitalIO driver of the dwf module.
        :param mask: the single bit mask of the pin.
        """
        self.dio = dio
        self.mask = mask
        self.config = self.Config.Input

    def _set_input(self):
        self.dio.outputEnableSet(self.dio.outputEnableGet() & ~self.mask)

    def _set_output(self):
        self.dio.outputEnableSet(self.dio.outputEnableGet() | self.mask)

    def _set(self):
        self.dio.outputSet(self.dio.outputGet() | self.mask)

    def _reset(self):
        self.dio.outputSet(self.dio.outputGet() & ~self.mask)

    def is_high(self) -> bool:
        """
        .. warning::
            This function does not return the actual pin state, only the set
            output state. Use `read()` for that instead.
        :return: `True` if the pin output state is set high.
        """
        return self.dio.outputGet() & self.mask

    def is_output(self) -> bool:
        """
        :return: `True` if pin is configured as output.
        """
        return self.dio.outputEnableGet() & self.mask

    def set_output(self, config: Config = None, level: Level = None):
        """
        Configures the pin as output with an initial level.
        :param config: pin hardware configuration. Default: `Config.PushPull`
        :param level: initial output level. Default: `Level.High`.
        """
        self.config = self.Config.PushPull if config is None else config
        self.set(level)

    def set(self, level: Level = None):
        """
        Sets an output level. Note that depending on pin configuration, the
        output level may not be achieved.

        :param level: output level. Default: `Level.High`.
        """
        if level is None: level = self.Level.High
        if self.config == self.Config.PushPull:
            if level: self._set()
            else: self._reset()
            self._set_output()
        elif self.config == self.Config.OpenDrain:
            if level:
                self._set_input()
            else:
                self._reset()
                self._set_output()
        elif self.config == self.Config.OpenSource:
            if level:
                self._set()
                self._set_output()
            else:
                self._set_input()

    def high(self):
        """
        Sets the output level to `Level.High`.
        """
        self.set(self.Level.High)

    def low(self):
        """
        Sets the output level to `Level.Low`.
        """
        self.set(self.Level.Low)

    def set_input(self):
        """
        Configures the pin as `Config.Input`.
        """
        self.config = self.Config.Input
        self._set_input()

    def read(self) -> bool:
        """
        :return: the actual input state of the pin.
        """
        return self.dio.inputStatus() & self.mask

# -----------------------------------------------------------------------------
class Digilent:
    """
    Wrapper class of the Digilent device.
    The [DWF Python API][dwf] is already very good and should be used directly
    to configure more advanced use-cases, so this class is very light-weight.
    """
    def __init__(self, device):
        """
        :param device: DWF device
        """
        self.dwf = device

    @lru_cache(100)
    def gpio(self, position: int) -> DigilentPin:
        """
        Creates a pin abstraction.
        :param position: Pin number
        """
        return DigilentPin(self.dwf.digitalIO, 1 << position)

    def _info_digital_io(self):
        info = ["",
            f"Enable Support  = {self.dwf.digitalIO.outputEnableInfo():032b}",
            f"Enabled         = {self.dwf.digitalIO.outputEnableGet():032b}",
            f"Output Support  = {self.dwf.digitalIO.outputInfo():032b}",
            f"Output High/Low = {self.dwf.digitalIO.outputGet():032b}",
            f"Input Support   = {self.dwf.digitalIO.inputInfo():032b}",
            f"Input Read      = {self.dwf.digitalIO.inputStatus():032b}",
        ]
        LOGGER.info("\n".join(info))
