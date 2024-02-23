# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define killme
    !killall -9 orbuculum
    !killall -9 orbtrace
    !killall -9 JLinkGDBServer
    !killall -9 openocd
    !killall -9 CrashDebug
    !killall -9 arm-none-eabi-gdb-py3
end
define hook-load
    px4_reset
end
define hookpost-load
    px4_reset
end
define hook-quit
    px4_switch_task -1
end
define hook-continue
    px4_switch_task -1
end
define hook-backtrace
    set disassemble-next-line off
end
define hookpost-backtrace
    set disassemble-next-line on
end
define px4_enable_vector_catch
    set *0xE000EDFC |= 0x07f0
end

define px4_log_start
    set pagination off
    set style enabled off
    set logging file $arg0
    set logging overwrite on
    set logging enabled on
end

define px4_log_stop
    set logging enabled off
    set style enabled on
end

define px4_fbreak
    break $arg0
    commands
        finish
        continue
    end
end

define px4_btfbreak
    break $arg0
    commands
        px4_backtrace
        finish
        continue
    end
end


define px4_breaktrace
    break $arg0
    px4_commands_backtrace
end

define px4_breaktrace10
    break $arg0
    px4_commands_backtrace10
end

define px4_breaktrace100
    break $arg0
    px4_commands_backtrace100
end

define px4_configure_orbuculum
    # send out sync packets every CYCCNT[28] ~268M cycles
    dwtSyncTap 3
    # enable the CYCCNT
    dwtCycEna 1
    # enable exception tracing
    dwtTraceException 1
    # Set POSTCNT source to CYCCNT[10] /1024
    dwtPostTap 1
    # Set POSTCNT init/reload value to /1 -> every 1024*2=2048 cycles = 9.5µs @ 216MHz
    dwtPostReset 2
    # enable PC sampling
    dwtSamplePC 0

    # Set the ITM ID to 1
    ITMId 1
    # Use processor clock
    ITMSWOEna 0
    # send global timestamp every 8192 cycles ~38µs, STM32 doesn't support this
    # ITMGTSFreq 2
    # timestamp prescaler /64, STM32 doesn't support this
    # ITMTSPrescale 3
    # Enable local timestamp generation
    ITMTSEna 1
    # DWT packets are forwarded to the ITM
    ITMTXEna 1
    # Sync packets are transmitted
    ITMSYNCEna 1

    # Enable ITM ports
    # We always need the task information
    set $TER = 0x0000000F
    # Enable workqueue scheduling
    set $TER |= 0x00000010

    # Enable semaphore profiling
    # set $TER |= 0x000000E0
    # Enable heap profiling
    # set $TER |= 0x00000F00
    # Enable DMA profiling
    # set $TER |= 0x00007000

    # Enable all optional user channels
    set $TER |= 0xFFFF0000

    # Write the TER to the device
    ITMTER 0 $TER
    # Enable the ITM
    ITMEna 1
end

define px4_enable_swo_stm32h7
    _setAddressesSTM32

    # DBGMCU_CR D3DBGCKEN D1DBGCKEN TRACECLKEN
    set *0x5C001004 = 0x00700007

    # Unlock SWTF_LAR
    set *($SWTFBASE+0xFB0) = 0xC5ACCE55
    # Enable ITM input of SWO trace funnel SWFT_CTRL
    set *($SWTFBASE+0x000) |= 0x00000001

    # Unlock SWO_LAR
    set *($SWOBASE+0xFB0) = 0xC5ACCE55
    # SWO current output divisor register
    # SWO_CODR = (rcc_pclk4 / SWO) - 1
    set *($SWOBASE+0x010) = ((480000000/4 / $arg0) - 1)
    # SWO selected pin protocol register SWO_SPPR
    set *($SWOBASE+0x0F0) = 0x00000002

    enableSTM32Pin 1 3 3
end

define px4_enable_trace_stm32h7
    _setAddressesSTM32

    # Setup PE2, PE3, PE4, PE5, and PE6
    enableSTM32Pin 4 2 3
    enableSTM32Pin 4 3 3
    if ($arg0 >= 2)
        enableSTM32Pin 4 4 3
    end
    if ($arg0 == 4)
        enableSTM32Pin 4 5 3
        enableSTM32Pin 4 6 3
    end

    # DBGMCU_CR D3DBGCKEN D1DBGCKEN TRACECLKEN
    set *0x5C001004 = 0x00700007

    # Unlock CSTF_LAR
    set *($CSTFBASE+0xFB0) = 0xC5ACCE55
    # Enable ITM input ENS1 of CoreSight trace funnel CSTF_CTRL
    set *($CSTFBASE+0x000) |= 0x00000003

    # Unlock ETF_LAR
    set *($ETFBASE+0xFB0) = 0xC5ACCE55
    # set Hardware FIFO mode in ETF_MODE
    set *($ETFBASE+0x028) = 0x00000002
    # Set EnFT and EnTI bits in ETF_FFCR
    set *($ETFBASE+0x304) = 0x00000003
    # Enable the trace capture in ETF_CTL
    set *($ETFBASE+0x020) = 0x00000001

    # Unlock TPIU_LAR
    set *($TPIUBASE+0xFB0) = 0xC5ACCE55
    # Write port size into TPIU_CURPSIZE
    set *($TPIUBASE+0x004) = (1 << ($arg0 - 1))
    # Set ENFCONT and TRIGIN in TPIU_FFCR
    set *($TPIUBASE+0x304) = 0x00000102
end

define px4_trace_tpiu_swo_stm32f7
    px4_reset
    tbreak nx_start
    continue

    enableSTM32TRACE 4 3

    px4_configure_orbuculum

    # -o trace.swo dumps the RAW data, not the demuxed data!!!
    shell killall orbuculum
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
    shell killall orbuculum
    shell orbuculum -O "-T4" -t1 &
    shell sleep 1
    shell nc localhost 3443 > trace.swo &
end
