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
    px4_root = Path(px4_root)
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
    px4_root = Path(px4_root)
    operations = [
        PatchOperation(px4_root, _data("disable_uavcan_v5x.patch")),
    ]
    return PatchManager("Make the Firmware fit on the FMUv5x Flash", operations)


def itm_logging(px4_root: Path) -> PatchManager:
    """
    Adds ITM access to NuttX as a driver.
    """
    px4_root = Path(px4_root)
    operations = [
        CopyOperation(_data("itm.h"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/include/nuttx/itm/itm.h"),
        CopyOperation(_data("itm_Make.defs"),
                      px4_root / "platforms/nuttx/NuttX/nuttx/drivers/itm/Make.defs"),
        PatchOperation(px4_root, _data("itm_nuttx_Makefile.patch")),
    ]
    return PatchManager("Add ITM access to NuttX", operations)


def nuttx_tracing_itm(px4_root: Path) -> PatchManager:
    """
    Adds scheduler and heap instrumentation to NuttX via ITM.
    Requires the `itm_logging` patch.
    """
    px4_root = Path(px4_root)
    operations = [
        PatchOperation(px4_root, _data("nuttx_tracing_itm.patch")),
    ]
    return PatchManager("Add tracing support to NuttX via ITM", operations)


def nuttx_sdmmc_reg_access(px4_root: Path) -> PatchManager:
    """
    Un-inlines the `sdmmc_putreg32`, `sdmmc_getreg32`, and `sdmmc_modifyreg32`
    functions, so that breakpoints can be set on them.
    """
    px4_root = Path(px4_root)
    operations = [
        PatchOperation(px4_root, _data("sdmmc_no_inline.patch")),
    ]
    return PatchManager("Un-inline SDMMC register access", operations)
