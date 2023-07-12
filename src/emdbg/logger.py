# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

import logging
import logging.config

VERBOSITY = 0
LEVEL = logging.WARNING


def configure(verbosity: int = None):
    """
    Configures the logging of the entire module.

    :param verbosity:
        Set the logging level: ≥-1: ERROR, ≥0: WARNING, ≥1: INFO, ≥2: DEBUG.
        Default is None=0=WARNING.
    """
    if verbosity is None:
        verbosity = 0

    global VERBOSITY
    VERBOSITY = verbosity

    global LEVEL
    if verbosity >= 2:
        LEVEL = logging.DEBUG
    elif verbosity == 1:
        LEVEL = logging.INFO
    elif verbosity == 0:
        LEVEL = logging.WARNING
    else:
        LEVEL = logging.ERROR

    # TODO: Custom logger configuration for only the emdbg module
    logging.basicConfig(level=LEVEL)

    # Disable some particularly chatty modules
    logging.getLogger("pygdbmi.IoManager").setLevel(logging.INFO)
    logging.getLogger("graphviz._tools").setLevel(logging.INFO)
