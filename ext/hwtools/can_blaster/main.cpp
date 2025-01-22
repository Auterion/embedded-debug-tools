// Copyright (c) 2025, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#include <modm/board.hpp>
#include <modm/processing.hpp>

static std::chrono::microseconds rate_sleep(1000us);
modm::Fiber fiber_parse_rate([]
{
    uint32_t rate_input{0};
    while(true)
    {
        // Poll the input UARTs for data bytes
        if (char c; modm::log::info.get(c), c != modm::IOStream::eof)
        {
            modm::log::info << c;
            // only allow hexadecimal numbers into the buffer
            if ('0' <= c and c <= '9')
            {
                rate_input *= 10;
                rate_input += c - '0';
            }
            // on ENTER key set the rate
            else if (c == '\r' or c == '\n')
            {
                modm::log::info << "Setting rate to " << rate_input << modm::endl;
                if (rate_input == 0) rate_sleep = 0us;
                else rate_sleep = std::chrono::microseconds(1'000'000ul / rate_input);
                rate_input = 0;
            }
        }
        modm::this_fiber::yield();
    }
});

// FIXME: This is a workaround for the missing Can1 in the SystemClock
struct Clock { static constexpr uint32_t Can1 = Board::SystemClock::Apb1; };

modm::Fiber fiber_generate([]
{
    using Can = modm::platform::Can1;
    Board::LedD13::setOutput();

    // D2=PA12=Tx and D10=PA11=Rx
    Can::connect<GpioA12::Tx, GpioA11::Rx>();
    (void) Can::initialize<Clock, 125_kbps>(5);
    RandomNumberGenerator::enable();

    uint32_t message_id = 0x1234'5678;
    uint64_t message_data = 0x1234'5678'90ab'cdef;
    while(true)
    {
        if (rate_sleep == 0us) {
            modm::this_fiber::sleep_for(1ms);
            continue;
        }
        modm::can::Message message(message_id, sizeof(uint64_t));
        message.setExtended(true);
        std::memcpy(message.data, &message_data, sizeof(uint64_t));
        Can::sendMessage(message);

        message_id += RandomNumberGenerator::getValue();
        message_data += RandomNumberGenerator::getValue();

        Board::LedD13::toggle();
        modm::this_fiber::sleep_for(rate_sleep);
    }
});

int
main()
{
    Board::initialize();

    modm::fiber::Scheduler::run();
    return 0;
}
