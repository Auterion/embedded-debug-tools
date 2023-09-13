# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

"""
.. include:: callgraph.md
"""

from __future__ import annotations
import re, os
import itertools
import logging
from pathlib import Path
from collections import defaultdict
from .backtrace import Backtrace
from .utils import read_gdb_log
LOGGER = logging.getLogger(__name__)


def callgraph_from_backtrace(backtraces: list[str],
                             BacktraceClass: Backtrace = None,
                             output_graphviz: Path = None,
                             output_pyvis: Path = None):
    """
    Convert a GDB backtrace log file into a dot, svg and pyvis file.

    :param backtraces: list of strings each containing a backtrace.
    :param BacktraceClass: One of the classes of `emdbg.analyze.backtrace`.
    :param output_graphviz: Output path of the graphviz file (`.dot` suffix).
        If you set its suffix to `.svg`, the `dot` command is used to generate
        a SVG file instead.
    :param output_pyvis: Output path to a pyvis file. (Requires the `pyvis`
        module to be installed).
    """

    if BacktraceClass is None:
        BacktraceClass = Backtrace

    backts = defaultdict(set)
    for description in backtraces:
        bt = BacktraceClass(description)
        if bt.is_valid:
            backts[bt.type].add(bt)
            # if bt.type == "unknown":
            #     print(bt)
            #     print(bt.description)
        else:
            LOGGER.error(bt)
            LOGGER.error(bt.description)

    nodes = {}
    edges = defaultdict(int)

    def itertools_pairwise(iterable):
        a, b = itertools.tee(iterable)
        next(b, None)
        return zip(a, b)

    for btype, bts in backts.items():
        for bt in bts:
            for frame in bt.frames:
                nodes[frame._unique_location] = frame
            for f1, f2 in itertools_pairwise(bt.frames):
                edges[(f2._unique_location, f1._unique_location, str((btype or "").lower()))] += 1

    sources = set(nodes)
    sinks = set(nodes)
    max_calls = max(edges.values())
    for source, sink, _ in edges.keys():
        sources.discard(sink)
        sinks.discard(source)

    def _n(name):
        return re.sub(r"[, :<>]", "_", name)

    if output_pyvis:
        import pyvis
        net = pyvis.network.Network(height="100%", width="100%", select_menu=True)
        for node in sorted(nodes):
            kwargs = {"label": node}
            if node in sinks:
                kwargs.update({"borderWidth": 3, "color": "LightBlue"})
            elif node in sources:
                kwargs.update({"borderWidth": 3, "color": "LightGreen"})
            net.add_node(_n(node), label=node)
        for edge in sorted(edges):
            net.add_edge(_n(edge[0]), _n(edge[1]), label=edge[2], arrows="to")
        net.toggle_physics(True)
        net.show(output_pyvis, notebook=False)

    if output_graphviz:
        output_graphviz = Path(output_graphviz)
        import graphviz
        dot = graphviz.Digraph()
        for node in sorted(nodes):
            frame = nodes[node]
            kwargs = {
                "label": f"{frame.function}:{frame.line}",
                "URL": f"subl://open?url={Path(frame.filename).absolute()}&line={frame.line}",
            }
            for pattern, style in BacktraceClass.COLORS.items():
                if re.search(pattern, node):
                    kwargs.update(style)
            if node in sinks:
                kwargs.update({"style": "bold,filled", "fillcolor": "LightBlue"})
            elif node in sources:
                kwargs.update({"style": "bold,filled", "fillcolor": "LightGreen"})
            dot.node(_n(node), **kwargs)
        for edge in sorted(edges):
            dot.edge(_n(edge[0]), _n(edge[1]), label=edge[2] or str(edges[edge]),
                     penwidth=str(max(edges[edge]/max_calls * 10, 0.5)))
        output_dot = output_graphviz.with_suffix(".dot")
        output_dot.write_text(dot.source)
        if output_graphviz.suffix == ".svg":
            os.system(f"dot -Tsvg -o {output_graphviz} {output_dot}")
            os.system(f"rm {output_dot}")


# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    from .backtrace import *

    parser = argparse.ArgumentParser(description="Backtrace Analyzer")
    parser.add_argument(
        "file",
        type=Path,
        help="The GDB log containing the backtraces.")
    parser.add_argument(
        "--graphviz",
        type=Path,
        help="The file to render the dot graph in.")
    parser.add_argument(
        "--svg",
        action="store_true",
        default=False,
        help="Render into SVG file using the same name as the input.")
    parser.add_argument(
        "--pyvis",
        type=Path,
        help="The file to render the pyvis graph in.")
    values = {
        "FileSystem": FileSystemBacktrace,
        "SPI": SpiBacktrace,
        "I2C": I2cBacktrace,
        "CAN": CanBacktrace,
        "UART": UartBacktrace,
        "Semaphore": SemaphoreBacktrace,
        "Generic": Backtrace,
    }
    parser.add_argument(
        "--type",
        choices=values.keys(),
        help="The backtrace class to use.")
    args = parser.parse_args()
    BacktraceClass = values.get(args.type)

    if BacktraceClass is None:
        if "_sdmmc" in args.file.name:
            BacktraceClass = FileSystemBacktrace
        elif "_spi" in args.file.name:
            BacktraceClass = SpiBacktrace
        elif "_i2c" in args.file.name:
            BacktraceClass = I2cBacktrace
        elif "_can" in args.file.name:
            BacktraceClass = CanBacktrace
        elif "_uart" in args.file.name:
            BacktraceClass = UartBacktrace
        elif "_semaphore" in args.file.name:
            BacktraceClass = SemaphoreBacktrace
        else:
            BacktraceClass = Backtrace

    graphviz = args.graphviz
    if args.svg:
        graphviz = Path(str(args.file.with_suffix(".svg")).replace("calltrace_", "callgraph_"))

    backtraces = re.split(r"(?:Breakpoint|Hardware .*?watchpoint) \d", read_gdb_log(args.file)[20:])
    callgraph_from_backtrace(backtraces, BacktraceClass,
                             output_graphviz=graphviz, output_pyvis=args.pyvis)
