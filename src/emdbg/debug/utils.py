# Copyright (c) 2020-2022, Niklas Hauser
# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause


def _listify(obj):
    if obj is None:
        return list()
    if isinstance(obj, (list, tuple, set, range)):
        return list(obj)
    if hasattr(obj, "__iter__") and not hasattr(obj, "__getitem__"):
        return list(obj)
    return [obj, ]


def listify(*objs):
    """
    Convert arguments to list if they are not already a list.
    """
    return [l for o in objs for l in _listify(o)]


def listrify(*objs):
    """
    Convert arguments to list of strings.
    """
    return list(map(str, listify(*objs)))
