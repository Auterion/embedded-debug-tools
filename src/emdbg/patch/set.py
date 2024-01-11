# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from pathlib import Path
from .operation import CopyOperation, PatchOperation, PatchManager

def _data(file: str) -> Path:
    return Path(__file__).parent / "data" / file


def semaphore_boostlog(px4_root: Path) -> PatchManager:
    """
    Enable runtime logging of task priority boosting through semaphores.
    This adds a lock-free 32 slot buffer containing task and priority information
    that is written from inside the kernel and read in the PX4 logger module,
    which logs it out to the NSH.
    """
    operations = [
        PatchOperation(px4_root, _data("semaphore_boostlog.patch")),
        CopyOperation(_data("sem_boostlog.c"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/sched/semaphore/sem_boostlog.c"),
        CopyOperation(_data("semaphore_boostlog.h"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/include/semaphore_boostlog.h"),
    ]
    return PatchManager("Logging of Task Priority Inheritance by Semaphores", operations)


def reduce_firmware_size_v5x(px4_root: Path) -> PatchManager:
    """
    Disables UAVCAN and a few drivers to make the binary size fit on the FMUv5x.
    """
    operations = [
        PatchOperation(px4_root, _data("disable_uavcan_v5x.patch")),
    ]
    return PatchManager("Make the Firmware fit on the FMUv5x Flash", operations)


def _nuttx_tracing_itm(px4_root: Path) -> list:
    operations = [
        CopyOperation(_data("itm.h"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/include/nuttx/itm/itm.h"),
        CopyOperation(_data("itm_Make.defs"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/drivers/itm/Make.defs"),
        PatchOperation(px4_root, _data("itm_nuttx_Makefile.patch")),
        PatchOperation(px4_root, _data("nuttx_tracing_itm.patch")),
    ]
    return operations

def nuttx_tracing_itm_v10(px4_root: Path) -> PatchManager:
    """
    Adds scheduler and heap instrumentation to NuttX v10 via ITM.
    """
    operations = _nuttx_tracing_itm(px4_root) + [
        PatchOperation(px4_root, _data("nuttx_tracing_itm_v10.patch")),
    ]
    return PatchManager("Add tracing support to NuttX v10 via ITM", operations)

def nuttx_tracing_itm_v11(px4_root: Path) -> PatchManager:
    """
    Adds scheduler and heap instrumentation to NuttX v11 via ITM.
    """
    operations = _nuttx_tracing_itm(px4_root) + [
        PatchOperation(px4_root, _data("nuttx_tracing_itm_v11.patch")),
    ]
    return PatchManager("Add tracing support to NuttX v11 via ITM", operations)


def nuttx_tracing_itm_uart4(px4_root: Path) -> PatchManager:
    """
    Trace data reception errors on UART4.
    """
    operations = [
        PatchOperation(px4_root, _data("nuttx_tracing_itm_uart4.patch")),
    ]
    return PatchManager("Trace data transmit/receive errors on UART4", operations)


def nuttx_sdmmc_reg_access(px4_root: Path) -> PatchManager:
    """
    Un-inlines the `sdmmc_putreg32`, `sdmmc_getreg32`, and `sdmmc_modifyreg32`
    functions, so that breakpoints can be set on them.
    """
    operations = [
        PatchOperation(px4_root, _data("sdmmc_no_inline.patch")),
    ]
    return PatchManager("Un-inline SDMMC register access", operations)


def malloc_return_null(px4_root: Path) -> PatchManager:
    """
    Instruments the mm_malloc in NuttX to fail if call count equals global
    `emdbg_malloc_count_null` variable, which is placed in `.noinit` section.
    You can use this to find code that doesn't check the malloc return value for
    NULL or see how the error handling performs.
    """
    operations = [
        PatchOperation(px4_root, _data("malloc_return_null.patch")),
    ]
    return PatchManager("Make the n-th malloc call return NULL", operations)
