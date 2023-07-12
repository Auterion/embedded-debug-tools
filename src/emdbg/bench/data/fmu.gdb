# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

define hook-load
    monitor reset
end
define hookpost-load
    monitor reset halt
end
define hook-quit
    px4_switch_task -1
end
define hook-continue
    px4_switch_task -1
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

define px4_commands_backtrace
    commands
        printf "%10uus> Task=%.25s\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), ((struct tcb_s *)g_readytorun->head)->name
        px4_backtrace
        continue
    end
end
define px4_commands_backtrace10
    commands
        printf "%10uus> Task=%.25s\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), ((struct tcb_s *)g_readytorun->head)->name
        px4_backtrace
        continue 10
    end
end
define px4_commands_backtrace100
    commands
        printf "%10uus> Task=%.25s\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), ((struct tcb_s *)g_readytorun->head)->name
        px4_backtrace
        continue 100
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



define px4_calltrace_sdmmc
    px4_breaktrace sdmmc_modifyreg32
    px4_breaktrace10 sdmmc_putreg32
    px4_breaktrace10 sdmmc_getreg32
end

define px4_calltrace_spi
    px4_breaktrace100 spi_putreg8
    px4_breaktrace100 spi_getreg8
    px4_breaktrace100 spi_putreg
    px4_breaktrace100 spi_getreg
end

define px4_calltrace_i2c
    px4_breaktrace100 stm32_i2c_getreg
    px4_breaktrace100 stm32_i2c_getreg32
    px4_breaktrace100 stm32_i2c_putreg
    px4_breaktrace100 stm32_i2c_putreg32
    px4_breaktrace100 stm32_i2c_modifyreg32
end

define px4_calltrace_can
    px4_breaktrace CanIface::init
    px4_breaktrace10 CanIface::send
    px4_breaktrace100 CanIface::receive
    px4_breaktrace100 TransferListener::handleFrame
end

define px4_calltrace_uart
    px4_breaktrace up_dma_setup
    px4_breaktrace up_setup
    px4_breaktrace100 up_serialin
    px4_breaktrace100 up_serialout
end

define px4_calltrace_uart
    px4_breaktrace up_dma_setup
    px4_breaktrace up_setup
    px4_breaktrace100 up_serialin
    px4_breaktrace100 up_serialout
end

define px4_calltrace_dma
    px4_breaktrace stm32_dmastart
    px4_breaktrace stm32_dmasetup
    px4_breaktrace stm32_dmaresidual
    px4_breaktrace stm32_dmastreamdisable
    px4_breaktrace stm32_dmainterrupt
end


define px4_calltrace_semaphore_boosts
    # Log every time a semaphore gets boosted
    px4_rbreak sem_holder.c:nxsem_boostholderprio:nxsched_set_priority\(htcb, *rtcb->sched_priority\);
    commands
        if $px4_valid(sem) == 1
            printf "L380 %10uus> %p: %25.25s %3d _/ %3d %.25s\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), sem, htcb->name, htcb->sched_priority, rtcb->sched_priority, rtcb->name
        end
        if $px4_valid(sem) == 0
            printf "L380 %10uus> <opti-out>: %25.25s %3d _/ %3d %.25s\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), htcb->name, htcb->sched_priority, rtcb->sched_priority, rtcb->name
        end
        px4_backtrace
        continue
    end

    # Log every time a semaphore gets unboosted
    px4_rbreak sem_holder.c:nxsem_restoreholderprio:nxsched_reprioritize\(htcb, *htcb->base_priority\);
    commands
        if $px4_valid(sem) == 1
            printf "L550 %10uus> %p: %25.25s %3d \\_ %3d\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), sem, htcb->name, htcb->sched_priority, htcb->base_priority
        end
        if $px4_valid(sem) == 0
            printf "L550 %10uus> <opti-out>: %25.25s %3d \\_ %3d\n", (hrt_absolute_time::base_time + *(uint16_t*)0x40010424), htcb->name, htcb->sched_priority, htcb->base_priority
        end
        px4_backtrace
        continue
    end
end


define px4_trace_swo
    monitor tpiu create itm.tpiu -dap [dap names] -ap-num 0
    monitor itm.tpiu configure -traceclk 216000000 -pin-freq 21600000 -protocol uart -output trace.swo -formatter 0
    monitor itm.tpiu enable
    monitor tpiu init
    monitor itm ports off
    # Enable scheduler reporting
    monitor itm port 0 on
    monitor itm port 1 on
    # Task suspensions are implicit before a task resume
    # monitor itm port 2 on
    monitor itm port 3 on
    monitor itm port 4 on
    # Enable semaphore reporting
    # monitor itm port 5 on
    # monitor itm port 6 on
    # Enable preemption lock reporting
    # monitor itm port 7 on
    # monitor itm port 8 on
    # Enable critical section lock reporting
    # monitor itm port 9 on
    # monitor itm port 10 on
    # Enable spinlock reporting
    # monitor itm port 11 on
    # monitor itm port 12 on
    # monitor itm port 13 on
    # monitor itm port 14 on

    # send out sync packets every CYCCNT[28] ~268M cycles
    dwtSyncTap 3
    # enable the CYCCNT
    dwtCycEna 1
    # enable exception tracing
    dwtTraceException 1
    # Set POSTCNT source to CYCCNT[10] /1024
    dwtPostTap 1
    # Set POSTCNT init/reload value to /1 -> every 1024*2=1024 cycles = 9.5µs
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
    # Enable the ITM
    ITMEna 1

    # Enable the SWO output
    enableSTM32SWO 4
end


