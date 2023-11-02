# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
from .base import Base


class UartBuffer(Base):
    """
    Pretty Printing UART buffers
    """

    def __init__(self, gdb, buf_ptr: "gdb.Value"):
        super().__init__(gdb)
        self._buf = buf_ptr

    def children(self) -> Iterator[tuple[str, Any]]:
        size, head, tail = self._buf['size'], self._buf['head'], self._buf['tail']
        used = head - tail if (tail <= head) else size - tail + head
        free = size - used
        yield ("sem", self._buf['sem'])
        yield ("size", size)
        yield ("buffer", self._buf['buffer'])
        yield ("tail -> head", f"{tail} -> {head}: {used} used, {free} free")
        if used:
            if (tail < head):
                # [tail, head]
                content = self.read_memory(self._buf['buffer'] + tail, used)
            else:
                # head], [tail
                content = self.read_memory(self._buf['buffer'] + tail, size - tail)
                content += self.read_memory(self._buf['buffer'], head)
            # Convert to Prints else \hh hex values
            content = "".join(chr(v) if chr(v).isprintable() else f"\\{v:02x}"
                              for v in content.tobytes())
            yield ("content", content)
