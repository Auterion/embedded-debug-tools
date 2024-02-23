# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

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

define px4_calltrace_spi_exchange
    px4_breaktrace spi_exchange
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
