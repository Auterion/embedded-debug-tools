# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import time
from yoctopuce.yocto_api import YAPI, YRefParam, YModule
from yoctopuce.yocto_relay import YRelay
from contextlib import contextmanager
from .base import Base
import logging
LOGGER = logging.getLogger("power:yocto")
YOCTO_HUB_COUNT = 0


class YoctopuceException(Exception):
    """Base exception for Yoctopuce-related errors."""
    def __init__(self, msg, context=None):
        """:param context: Contains the `yoctopuce.yocto_api.YRefParam` error message"""
        Exception.__init__(self, msg)
        self.context = context


@contextmanager
def _yoctopuce_hub(location=None):
    """
    Registers the hub and frees the YAPI. Can be called multiple times.

    :raises `YoctopuceException`: if hub cannot be registered.
    """
    global YOCTO_HUB_COUNT
    try:
        LOGGER.info("Starting...")
        errmsg = YRefParam()
        if YAPI.RegisterHub(location or "usb", errmsg) != YAPI.SUCCESS:
            raise YoctopuceException("Yoctopuce RegisterHub failed!", errmsg)
        YOCTO_HUB_COUNT += 1
        yield
    finally:
        LOGGER.debug("Stopping.")
        if YOCTO_HUB_COUNT > 0:
            YOCTO_HUB_COUNT -= 1
        if YOCTO_HUB_COUNT == 0:
            YAPI.FreeAPI()


@contextmanager
def relay(channel: int = 0, inverted: bool = False, relay=None, location=None):
    """
    Context manager for starting and stopping the Yocto API and instantiating a
    `Relay` object.

    :param channel: Relays with multiple channels get their own object per channel.
    :param inverted: Inverts the output state of the relay channel.
    :param relay: Pass an existing `yoctopuce.relay.YRelay` object or
                  find the first available one.
    :param location: Location of Yoctopuce Hub or automatically find it.

    :raises `YoctopuceException`: if hub cannot be registered, relay is not
                                  connected, not online or cannot be found.

    :return: a `Relay` object.
    """
    with _yoctopuce_hub(location):
        yield Relay(channel, inverted, relay)


def _first_yoctopuce_relay(channel=0):
    """Finds the right channel"""
    relay = YRelay.FirstRelay()
    if relay is None:
        raise YoctopuceException("No relay connected!")
    if not relay.isOnline():
        raise YoctopuceException("Relay is not online!", relay)

    serial = relay.get_module().get_serialNumber()
    LOGGER.debug(f"Using first found relay '{serial}'")
    return YRelay.FindRelay(f"{serial}.relay{channel}")


class Relay(Base):
    """
    Light Wrapper around the [Yocto-Relay API][yp].
    Each channel is accessed by its own object.

    [yp]: https://www.yoctopuce.com/EN/products/yocto-relay/doc/RELAYLO1.usermanual.html
    """
    def __init__(self, channel: int = 0, inverted: bool = False, relay=None):
        """
        :param channel: Relays with multiple channels get their own object per channel.
        :param inverted: Inverts the output state of the relay channel.
        :param relay: Pass an existing `yoctopuce.relay.YRelay` object or
                      find the first available one.

        :raises `YoctopuceException`: if relay is not connected, not online or cannot be found.
        """
        super().__init__()
        self.relay = relay or _first_yoctopuce_relay(channel)
        self.channel = channel
        self._map = (YRelay.STATE_B, YRelay.STATE_A) if inverted else (YRelay.STATE_A, YRelay.STATE_B)
        self._on = lambda: self.relay.set_state(self._map[0])
        self._off = lambda: self.relay.set_state(self._map[1])


if __name__ == "__main__":
    import emdbg
    import argparse

    parser = argparse.ArgumentParser(
        description="Have you tried turning it off and on again?")
    parser.add_argument(
        "command",
        choices=["on", "off", "cycle"],
        help="Turn on and off.")
    parser.add_argument(
        "--channel",
        type=int,
        default=0,
        help="The channel of the relay.")
    parser.add_argument(
        "--inverted",
        action="store_true",
        default=False,
        help="Channel is inverted.")
    parser.add_argument(
        "--location",
        help="Location of Yoctopuce hub.")
    parser.add_argument(
        "--time",
        type=int,
        default=1,
        help="Location of Yoctopuce hub.")
    parser.add_argument(
        "-v",
        dest="verbosity",
        action="count",
        help="Verbosity level.")
    args = parser.parse_args()
    emdbg.logger.configure(args.verbosity)

    with relay(args.channel, args.inverted, args.location) as pwr:
        if args.command == "on":
            pwr.on(args.time)
        elif args.command == "off":
            pwr.off(args.time)
        elif args.command == "cycle":
            pwr.cycle(args.time, args.time)
