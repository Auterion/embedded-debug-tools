// Copyright (c) 2025, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#include <modm/board.hpp>
#include <modm/processing.hpp>

static modm::ShortPeriodicTimer tmr{0.5s};
static modm::can::Message message;

using Can = modm::platform::Can1;
// FIXME: This is a workaround for the missing Can1 in the SystemClock
struct Clock { static constexpr uint32_t Can1 = Board::SystemClock::Apb1; };

int
main()
{
    Board::initialize();
    Board::LedD13::setOutput(modm::Gpio::Low);

    // Pins for D10=Rx, D2=Tx
    Can::connect<GpioA11::Rx, GpioA12::Tx>(Gpio::InputType::PullUp);
    (void) Can::initialize<Clock, 125_kbps>(5);
    CanFilter::setFilter(0, CanFilter::FIFO0,
                         CanFilter::ExtendedIdentifier(0),
                         CanFilter::ExtendedFilterMask(0));

    while(1)
    {
        if (Can::isMessageAvailable())
        {
            Can::getMessage(message);
            // Send message back
            Can::sendMessage(message);
        }
        if (tmr.execute()) Board::LedD13::toggle();
    }

    return 0;
}
