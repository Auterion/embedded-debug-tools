# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_enable_vector_catch
    set *0xE000EDFC |= 0x07f0
end

define px4_reset
    monitor reset 2
    px4_enable_vector_catch
end

# $arg0: TER register value
# $arg1: SWO frequency
define px4_trace_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue
    monitor SWO EnableTarget 216000000 $arg1 1 0
    px4_configure_orbuculum $arg0
    shell nc localhost 2332 > trace.swo &
end

# $arg0: TER register value
# $arg1: SWO frequency
define px4_trace_swo_stm32h7
    px4_reset
    tbreak nx_start
    continue
    monitor SWO EnableTarget 120000000 $arg1 1 0
    px4_configure_orbuculum $arg0
    shell nc localhost 2332 > trace.swo &
end
