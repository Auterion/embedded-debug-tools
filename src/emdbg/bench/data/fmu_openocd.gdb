# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_reset
    monitor reset halt
end

define px4_trace_swo_v5x
    px4_reset
    monitor tpiu create itm.tpiu -dap [dap names] -ap-num 0
    monitor itm.tpiu configure -traceclk 216000000 -pin-freq 21600000 -protocol uart -output trace.swo -formatter 0
    monitor itm.tpiu enable
    monitor tpiu init
    monitor itm ports off

    px4_trace_swo_gdb

    # Enable the SWO output
    enableSTM32SWO 4
end
