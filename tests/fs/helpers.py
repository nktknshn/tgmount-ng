import os
from collections.abc import Awaitable, Callable
from typing import Any

import aiofiles
import pytest

from tests.helpers.mount import cleanup_async
from tests.helpers.mount_context import MountContext
from tests.integrational.integrational_test import run_test
from tgmount import fs, vfs
from tgmount.fs import FileSystemOperations
from tgmount.main.util import mount_ops

from tgmount import tglog
from ..helpers.fixtures_common import mnt_dir


async def main_function(*, ops: fs.FileSystemOperations, mnt_dir: str):
    await mount_ops(
        ops,
        mount_dir=mnt_dir,
        min_tasks=10,
        fsname="tgmount_test_fs",
    )


class Context(MountContext):
    def __init__(self, mnt_dir: str, caplog=None) -> None:
        self.mnt_dir = mnt_dir
        self.caplog = caplog
        self._debug = False


    async def run_test(
        self,
        ops: Callable[[], FileSystemOperations],
        test_func: Callable[[], Awaitable[Any]],
    ):
        try:
            await run_test(
                main_function(ops=ops(), mnt_dir=self.mnt_dir),
                test_func(),
            )
        except Exception as e:
            raise e
        finally:
            await cleanup_async(self.mnt_dir)
