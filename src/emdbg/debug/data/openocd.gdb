# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

# $arg0: TER register value
# $arg1: SWO frequency
define px4_trace_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue

    shell rm -f trace.swo
    monitor tpiu create itm.tpiu -dap [dap names] -ap-num 0
    monitor itm.tpiu configure -traceclk 216000000 -pin-freq $arg1 -protocol uart -output trace.swo -formatter 0
    monitor itm.tpiu enable
    monitor tpiu init
    monitor itm ports off

    px4_configure_orbuculum $arg0

    enableSTM32SWO 7
end

# $arg0: TER register value
# $arg1: SWO frequency
define px4_trace_swo_stm32h7
    px4_reset
    tbreak nx_start
    continue

    px4_enable_swo_stm32h7 $arg1

    px4_configure_orbuculum $arg0

    shell orbuculum -O "-Tu -a $arg1" -o trace.swo &
end
