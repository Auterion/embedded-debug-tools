# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_reset
    monitor reset 2
    px4_enable_vector_catch
end

define px4_trace_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue
    monitor SWO EnableTarget 216000000 27000000 1 0
    px4_configure_orbuculum
    shell nc localhost 2332 > trace.swo &
end

define px4_trace_swo_stm32h7
    px4_reset
    tbreak nx_start
    continue
    monitor SWO EnableTarget 120000000 30000000 1 0
    px4_configure_orbuculum
    shell nc localhost 2332 > trace.swo &
end
