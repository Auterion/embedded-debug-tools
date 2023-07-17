# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from pathlib import Path


def add_datetime(filename: Path | str):
    """
    Appends a filename with the current date and time:
    `Year_Month_Day_Hour_Minute_Second`

    Example: `path/name.txt` -> `path/name_2023_04_14_15_03_24.txt`
    """
    from emdbg.debug.px4.utils import add_datetime as _dt
    return _dt(filename)
