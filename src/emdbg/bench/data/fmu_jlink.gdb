# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define px4_reset
    monitor reset
end

define px4_trace_swo_v5x
    px4_reset
    monitor SWO EnableTarget 216000000 27000000 1 0
    px4_trace_swo_gdb
    shell nc localhost 2332 > trace.swo &
end

define px4_trace_swo_v6x
    px4_reset
    monitor SWO EnableTarget 120000000 30000000 1 0
    px4_trace_swo_gdb
    shell nc localhost 2332 > trace.swo &
end
