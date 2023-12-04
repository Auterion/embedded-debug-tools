# Copyright (c) 2023, Auterion AG
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations
import os
import shutil
import subprocess
import hashlib
from pathlib import Path
from contextlib import contextmanager
import logging
LOGGER = logging.getLogger("patch:ops")

def _repopath(path: str = None) -> Path:
    return Path(__file__).parents[1] / (path or "")

class OperationError(Exception):
    """Base exception for patching-related errors."""
    pass

# -----------------------------------------------------------------------------
class CopyOperation:
    """
    Copies a file from the store to the repository and removes it again.

    In case the destination location already exists, the file is stored in a
    cache, then overwritten. On restore, the cached file is copied back
    Note that you can set `src` to `None` if you want to remove a file inside
    the repository.
    """
    PATCH_STORE = _repopath(".patch_store")

    def __init__(self, source: Path, destination: Path):
        """
        :param source: File to copy into the repository. If set to `None`, the
                       destination file is simply removed.
        :param destination: File to add or overwrite. In case, the file exists,
                            it is copied to the `.patch_store` folder from where
                            it is copied back when restoring.
        """
        self._src = None
        self._dst = Path(destination)
        self._hash = str(self._dst.absolute())
        if source is not None:
            self._src = Path(source)
            self._hash += str(self._src.absolute())
        self._hash = hashlib.md5(self._hash.encode("utf-8")).hexdigest()
        self._store = self.PATCH_STORE / str(self._hash)
        self._dstrestore = self._store / self._dst.name

    def test_do(self) -> bool:
        return True

    def test_undo(self) -> bool:
        return True

    def do(self) -> bool:
        """
        Copies the `source` file to the `destination` location.
        If the destination exists, it is copied to the `.patch_store`, before
        getting overwritten by the source.

        :return: `True` if applied successfully.
        """
        if self._dst.exists():
            LOGGER.debug(f"Caching {self._dst} -> {self._dstrestore}")
            self._store.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._dst, self._dstrestore)
        if self._src is not None:
            LOGGER.debug(f"Copying {self._src} -> {self._dst}")
            self._dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self._src, self._dst)
        return True

    def undo(self) -> bool:
        """
        Removes the source file and copies the original destination file if it
        is found in the `.patch_store` folder.

        :return: `True` if restored successfully.
        """
        LOGGER.debug(f"Removing {self._dst}")
        self._dst.unlink(missing_ok=True)
        if self._dstrestore.exists():
            LOGGER.debug(f"Uncaching {self._dstrestore} -> {self._dst}")
            shutil.copy2(self._dstrestore, self._dst)
            self._dstrestore.unlink()
        return True

    def __repr__(self) -> str:
        if self._src is None:
            return f"Copy(Store <- {self._dst.name})"
        if self._src.name == self._dst.name:
            return f"Copy({self._dst.name})"
        return f"Copy({self._src.name} -> {self._dst.name})"


class PatchOperation:
    """
    Applies a patch in unified diff format to a directory.
    You can generate the patch from a git commit: `git format-patch -1 <sha>`.
    However, there are many more methods that generate unified diffs.
    """
    def __init__(self, root: Path, patch: Path):
        """
        :param root: directory to relocate the relative paths inside the patch to.
        :param patch: path to patch in unified diff format.

        :raises ValueError: if patch does not exists, or it cannot be parsed.
        """
        self._root = Path(root).absolute().resolve()
        self._patch = Path(patch).absolute().resolve()
        self._cmd = "patch --strip=1 --forward --ignore-whitespace --reject-file=- " \
                    f"--posix --directory={self._root} --input={self._patch} --silent"
        self._cmd_rev = self._cmd + " --reverse"
        self._cmd_check = " --dry-run"

    def test_do(self) -> bool:
        cmd_check = self._cmd + self._cmd_check
        if subprocess.run(cmd_check, shell=True).returncode:
            LOGGER.debug(cmd_check)
            return False
        return True

    def test_undo(self) -> bool:
        cmd_check = self._cmd_rev + self._cmd_check
        if subprocess.run(cmd_check, shell=True).returncode:
            LOGGER.debug(cmd_check)
            return False
        return True

    def do(self) -> bool:
        """
        Applies the patch to the directory.

        :return: `True` if applied successfully.
        """
        LOGGER.debug(f"Applying patch {self._patch}")
        if not self.test_do(): return False
        LOGGER.debug(self._cmd)
        return not subprocess.run(self._cmd, shell=True).returncode

    def undo(self) -> bool:
        """
        Applies the reversed patch to the directory.

        :return: `True` if restored successfully.
        """
        LOGGER.debug(f"Reverting patch {self._patch}")
        if not self.test_undo(): return False
        LOGGER.debug(self._cmd_rev)
        return not subprocess.run(self._cmd_rev, shell=True).returncode

    def __repr__(self) -> str:
        return f"Patch({self._patch.name})"


# -----------------------------------------------------------------------------
class PatchManager:
    """
    Stores a number of named operations and applies them all.
    """
    def __init__(self, name: str, ops: list[CopyOperation|PatchOperation]):
        """
        :param name: Short, human-readable name of patch.
        :param ops: list of operations.
        """
        self.name = name
        # make sure that PatchOperations happen first, since they can fail
        self._ops = sorted(ops, key=lambda o: isinstance(o, CopyOperation))

    def do(self):
        """
        Runs all operations to apply the patch. All operations are attempted
        even if any of them fail.

        :raises `OperationError`: if any of the operations failed.
        """
        LOGGER.info(f"Applying '{self.name}'")
        for op in self._ops:
            if not op.test_do():
                raise OperationError(f"Patching failed: {op}")
        for op in self._ops:
            if not op.do():
                raise OperationError(f"Patching failed: {op}")

    def undo(self):
        """
        Runs all operations to apply the patch. All operations are attempted
        even if any of them fail.

        :raises `OperationError`: if any of the operations failed.
        """
        LOGGER.info(f"Restoring '{self.name}'")
        for op in self._ops:
            if not op.test_undo():
                raise OperationError(f"Reverting failed: {op}")
        for op in self._ops:
            if not op.undo():
                raise OperationError(f"Reverting failed: {op}")

    @contextmanager
    def apply(self):
        """
        Context manager version to apply and restore the patch within a scope.

        ```py
        # patch repository
        with patch.apply():
            # run tests here
        # restore repository
        ```
        """
        try:
            self.do()
            yield
        finally:
            self.undo()
