// Copyright (c) 2024, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#pragma once

#include <unordered_map>
#include <string_view>
#include <cstdint>

// enum for skynode device id
enum DeviceId
{
    SYKNODE_V5X = 0,
    SYKNODE_V6X = 1,
    SKYNODE_S = 2,
};

class Device
{
public:
    using IrqTable = std::unordered_map<int16_t, std::string_view>;
    using RegisterTable = std::unordered_map<uint32_t, std::string_view>;
    Device() = default;

    /// @param hint device name or ELF filename.
    explicit Device(std::string_view hint);

    /// @return true if the device is valid.
    bool
    valid() const
    { return _irq_table; }

    /// Provides the IRQ table for a given device.
    const std::string_view
    irq(int16_t irq) const
    {
        if (_irq_table and _irq_table->contains(irq))
            return _irq_table->at(irq);
        return "unknown";
    }

    /// Provides largest IRQ number.
    int16_t
    max_irq() const
    { return _max_irq; }

    const std::string_view
    register_name(uint32_t addr) const
    {
        if (_register_table and _register_table->contains(addr))
            return _register_table->at(addr);
        return "";
    }

    /// Provides the clock frequency for a given device.
    uint32_t
    clock() const
    { return _clock; }

    /// Provides the device id.
    int
    id() const
    { return (int)_id; }


private:
    const IrqTable *_irq_table{nullptr};
    const RegisterTable *_register_table{nullptr};
    uint32_t _clock{0};
    int16_t _max_irq{0};
    DeviceId _id; // device id: 0
};
