# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_reset
    monitor reset halt
    px4_enable_vector_catch
end

define px4_trace_swo_stm32f7
    px4_reset
    shell rm -f trace.swo
    monitor tpiu create itm.tpiu -dap [dap names] -ap-num 0
    monitor itm.tpiu configure -traceclk 216000000 -pin-freq 21600000 -protocol uart -output trace.swo -formatter 0
    monitor itm.tpiu enable
    monitor tpiu init
    monitor itm ports off

    px4_configure_orbuculum

    # Enable the SWO output
    enableSTM32SWO 7
end

define px4_trace_stm32f7
    px4_reset

    # Enable the ETM output
    enableSTM32TRACE 4 3

    px4_configure_orbuculum
end
