from abc import abstractmethod
import asyncio
import functools
import logging
from re import L
from typing import Awaitable, Callable, Optional
import pytest
from tests.helpers.mocked.mocked_client import MockedClientReader, MockedClientWriter
from tests.helpers.mocked.mocked_message import (
    MockedMessageWithDocument,
    MockedReactions,
)
from tests.helpers.mocked.mocked_storage import MockedTelegramStorage
from tests.integrational.integrational_test import MockedTgmountBuilderBase

import tgmount
from tests.integrational.helpers import mdict
from tests.helpers.config import create_config
from tests.integrational.context import Context
from tgmount.common.extra import Extra
from tgmount.config.config import DirConfigReader
from tgmount.config.config_type import ConfigRootParserProto
from tgmount.fs.operations import FileSystemOperations
from tgmount.tgclient.client_types import TgmountTelegramClientSendFileProto
from tgmount.tgclient.types import EntityId
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tgmount import extensions
from tgmount.tgmount.extensions.writable import (
    TgmountExtensionWritable,
    VfsTreeProducerExtensionProto,
    VfsDirTreeExtraWritable,
    VfsTreeWritable,
)
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir, VfsTreeDirContent
from tgmount.tgmount.vfs_tree_producer import VfsTreeProducer
from tgmount.tgmount.vfs_tree_producer_types import VfsDirConfig
from tgmount.util import map_none, yes
from tgmount.util.col import bytearray_write
from tgmount.vfs.types.dir import DirContentWritableProto
from tgmount.vfs.types.file import FileContentWritableProto, FileLike
from tgmount.fs.writable import FileSystemOperationsWritable
from telethon import types

from .fixtures import *
from ..logger import logger


def test_bytearray_write():
    data = bytearray()

    bytearray_write(data, 0, b"HELLO")
    assert data == b"HELLO"
    bytearray_write(data, 1, b"HELLO")
    assert data == b"HHELLO"
    bytearray_write(data, 7, b"HHELLOHELLO")


class Client(MockedClientWriter, MockedClientReader):
    def __init__(
        self, storage: MockedTelegramStorage, sender=None, notify=True
    ) -> None:
        MockedClientWriter.__init__(self, storage, sender, notify)
        MockedClientReader.__init__(self, storage)


class MockedTgmountBuilderBaseWritable(MockedTgmountBuilderBase):
    VfsTree = VfsTreeWritable
    TelegramClient = Client
    FileSystemOperations = FileSystemOperationsWritable

    extensions = [TgmountExtensionWritable()]

    async def create_client(self, cfg, **kwargs):
        return Client(storage=self._storage, notify=False)

    def __init__(self, storage: MockedTelegramStorage) -> None:
        logger.debug("MockedTgmountBuilderBaseWritable()")
        super().__init__(storage)


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
        root={"source": "source1", "upload": True},
        extensions={
            DirConfigReader: [TgmountExtensionWritable()],
        },
    )

    async def test():
        fs: FileSystemOperationsWritable = ctx.shared["fs"]
        tgm: TgmountBase = ctx.shared["tgm"]

        msg1 = await source1.message("text message 1")
        assert await ctx.listdir("/") == ["1_message.txt"]

        # upload happens on file close
        async with await ctx.open("/file2.txt", "w") as f:
            await f.write("HELLO")

        assert await ctx.read_text("/2_file2.txt") == "HELLO"

        assert await ctx.listdir("/") == ["1_message.txt", "2_file2.txt"]

        await ctx.remove("/2_file2.txt")

        assert await ctx.listdir("/") == ["1_message.txt"]

        # tgm.vfs_tree.

    await ctx.run_test(test, cfg_or_root=config)
