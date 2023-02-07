import logging
import pytest
from tests.helpers.mocked.mocked_message import MockedReactions
from tests.helpers.mocked.mocked_storage import MockedTelegramStorage
from tests.integrational.integrational_test import MockedTgmountBuilderBase

import tgmount
from tests.integrational.helpers import mdict
from tests.helpers.config import create_config
from tests.integrational.context import Context
from tgmount.config.config_type import ConfigRootParserProto
from tgmount.fs.operations import FileSystemOperations
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir, VfsTreeDirContent
from tgmount.vfs.types.dir import DirContentWritableProto
from tgmount.vfs.types.file import FileLike
from tgmount.fs.writable import FileSystemOperationsWritable

from .fixtures import *
from ..logger import logger


class TgmountBaseWritable(TgmountBase):
    FileSystemOperations = FileSystemOperationsWritable

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        logger.debug("TgmountBaseWritable()")


class VfsTreeDirContentWritable(VfsTreeDirContent, DirContentWritableProto):
    def __init__(self, tree: "VfsTree", path: str) -> None:
        super().__init__(tree, path)

    async def create(self, filename: str) -> FileLike:
        thedir = await self._tree.get_dir(self._path)
        filelike = vfs.FileLike(
            filename, content=vfs.FileContentStringWritable(), writable=True
        )
        await thedir.put_content(filelike)

        return filelike


class VfsTreeWritable(VfsTree):
    VfsTreeDirContent = VfsTreeDirContentWritable

    def __init__(self) -> None:
        logger.debug("VfsTreeWritable()")

        super().__init__()


class MockedTgmountBuilderBaseWritable(MockedTgmountBuilderBase):
    def __init__(self, storage: MockedTelegramStorage) -> None:
        logger.debug("MockedTgmountBuilderBaseWritable()")
        super().__init__(storage)

    VfsTree = VfsTreeWritable
    TgmountBase = TgmountBaseWritable


class TgmountIntegrationContextWritable(TgmountIntegrationContext):
    MockedTgmountBuilderBase = MockedTgmountBuilderBaseWritable

    def __init__(self, mnt_dir: str, *, caplog=None) -> None:
        super().__init__(mnt_dir, caplog=caplog)


@pytest.mark.asyncio
async def test_simple1(fixtures: Fixtures):
    ctx = TgmountIntegrationContextWritable(fixtures.mnt_dir, caplog=fixtures.caplog)
    source1 = ctx.storage.create_entity("source1")

    ctx.init_logging(logging.DEBUG, debug_fs_ops=True)

    config = create_config(
        message_sources={"source1": "source1"},
        root={"source": "source1"},
    )

    async def test():
        msg1 = await source1.message("text message 1")
        assert await ctx.listdir("/") == ["1_message.txt"]

        async with await ctx.open("/source1/file2.txt", "w") as f:
            await f.write("HELLO")

    await ctx.run_test(test, cfg_or_root=config)
