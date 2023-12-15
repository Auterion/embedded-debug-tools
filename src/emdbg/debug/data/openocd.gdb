# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_reset
    monitor reset halt
    px4_enable_vector_catch
end

define px4_trace_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue

    shell rm -f trace.swo
    monitor tpiu create itm.tpiu -dap [dap names] -ap-num 0
    monitor itm.tpiu configure -traceclk 216000000 -pin-freq 21600000 -protocol uart -output trace.swo -formatter 0
    monitor itm.tpiu enable
    monitor tpiu init
    monitor itm ports off

    px4_configure_orbuculum

    enableSTM32SWO 7
end


define px4_trace_swo_stm32h7
    px4_reset
    tbreak nx_start
    continue

    px4_enable_swo_stm32h7 60000000

    px4_configure_orbuculum

    shell orbuculum -O "-Tu -a 60000000" -o trace.swo &
end


define px4_trace_tpiu_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue

    enableSTM32TRACE 4 3

    px4_configure_orbuculum

    # -o trace.swo dumps the RAW data, not the demuxed data!!!
    shell orbuculum -O "-T4" -t1 &
    shell sleep 1
    shell nc localhost 3443 > trace.swo &
end


define px4_trace_tpiu_swo_stm32h7
    px4_reset
    tbreak nx_start
    continue

    px4_enable_trace_stm32h7 4

    px4_configure_orbuculum

    # -o trace.swo dumps the RAW data, not the demuxed data!!!
    shell orbuculum -O "-T4" -t1 &
    shell sleep 1
    shell nc localhost 3443 > trace.swo &
end
