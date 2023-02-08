from abc import abstractmethod
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
    TgmountVfsTreeProducerExtension,
    VfsDirTreeExtraWritable,
)
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir, VfsTreeDirContent
from tgmount.tgmount.vfs_tree_producer import VfsTreeProducer
from tgmount.tgmount.vfs_tree_producer_types import VfsDirConfig
from tgmount.util import map_none, yes
from tgmount.vfs.types.dir import DirContentWritableProto
from tgmount.vfs.types.file import FileContentWritableProto, FileLike
from tgmount.fs.writable import FileSystemOperationsWritable
from telethon import types

from .fixtures import *
from ..logger import logger


def bytearray_write(target: bytearray, offset: int, buf: bytes):
    target_len = len(target)

    for idx, b in enumerate(buf):
        if offset + idx >= target_len:
            target.append(b)
        else:
            target[offset + idx] = b


def test_bytearray_write():
    data = bytearray()

    bytearray_write(data, 0, b"HELLO")

    assert data == b"HELLO"


class FileContentWritableConsumer(FileContentWritableProto):
    """Consumes all the bytes. The result will be available in `close_func`"""

    size: int = 0

    def __init__(self) -> None:
        self._data: bytearray = bytearray()
        # self._consumed = False

    async def seek_func(self, handle, n: int, w: int):
        raise NotImplementedError()

    async def read_func(self, handle, off: int, size: int) -> bytes:
        raise NotImplementedError()

    tell_func: Optional[Callable[[Any], Awaitable[int]]] = None

    async def write(self, handle: None, off: int, buf: bytes):
        try:
            bytearray_write(self._data, off, buf)
        except Exception as e:
            logger.error(f"error: {e}")
        self.size = len(self._data)
        return len(buf)

    @abstractmethod
    async def open_func(self) -> None:
        return

    @abstractmethod
    async def close_func(self, handle):
        return


class FileContentWritableUpload(FileContentWritableConsumer):
    def __init__(self, uploader: TelegramFileUploader, filename: str) -> None:
        super().__init__()
        self._uploader = uploader
        self._filename = filename

    async def open_func(self) -> None:
        pass

    async def close_func(self, handle):
        await self._uploader.upload(
            bytes(self._data),
            file_name=self._filename,
        )


class TgmountBaseWritable(TgmountBase):
    FileSystemOperations = FileSystemOperationsWritable

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        logger.debug("TgmountBaseWritable()")


class VfsTreeDirContentWritable(VfsTreeDirContent, DirContentWritableProto):
    def __init__(
        self, tree: "VfsTree", path: str, uploader: TelegramFileUploader
    ) -> None:
        super().__init__(tree, path)
        self._uploader = uploader

    async def create(self, filename: str) -> FileLike:
        logger.debug(f"VfsTreeDirContentWritable.create({filename})")
        thedir = await self._tree.get_dir(self._path)

        filelike = vfs.FileLike(
            filename,
            content=FileContentWritableUpload(self._uploader, filename),
            writable=True,
        )

        return filelike


class VfsTreeProducerWritable(VfsTreeProducer):
    extensions = [TgmountExtensionWritable()]

    def __init__(self) -> None:
        super().__init__()

    async def produce_from_vfs_dir_config(
        self,
        resources: TgmountResources,
        tree_dir: VfsTreeDir | VfsTree,
        path: str,
        vfs_config: VfsDirConfig,
    ):
        tree_dir = await super().produce_from_vfs_dir_config(
            resources, tree_dir, path, vfs_config
        )

        for ext in self.extensions:
            await ext.extend_vfs_tree_dir(resources, vfs_config, tree_dir)

        return tree_dir


class VfsTreeDirWritable(VfsTreeDir):
    def __init__(
        self, tree: "VfsTree", path: str, wrappers=None, extra: Extra | None = None
    ) -> None:
        super().__init__(tree, path, wrappers, extra)


class VfsTreeWritable(VfsTree):
    VfsTreeDirContent = VfsTreeDirContent
    VfsTreeDir = VfsTreeDirWritable

    def __init__(self) -> None:
        logger.debug("VfsTreeWritable()")
        super().__init__()

    async def get_dir_content(self, path: str = "/") -> VfsTreeDirContent:
        # return await super().get_dir_content(path)
        d = await self.get_dir(path)

        writable = map_none(
            d.extra, lambda e: e.get("writable", VfsDirTreeExtraWritable)
        )

        if yes(writable) and yes(writable.uploader):
            return VfsTreeDirContentWritable(self, path, writable.uploader)

        return VfsTreeDirContent(self, path)


# class Client(MockedClientWriter, TgmountTelegramClientSendFileProto):
#     def __init__(self, storage: MockedTelegramStorage) -> None:
#         super().__init__(storage)

#     async def send_file(
#         self,
#         entity: EntityId,
#         file: str,
#         *,
#         caption: str | None = None,
#         voice_note: bool = False,
#         video_note: bool = False,
#         force_document=False,
#     ) -> MockedMessageWithDocument:
#         return await self._storage.get_entity(entity).document(file)
#         # return await super().send_file(entity, file, caption=caption, voice_note, video_note, force_document)


class Client(MockedClientWriter, MockedClientReader):
    def __init__(self, storage: MockedTelegramStorage, sender=None) -> None:
        super().__init__(storage, sender)


class MockedTgmountBuilderBaseWritable(MockedTgmountBuilderBase):
    VfsTree = VfsTreeWritable
    TgmountBase = TgmountBaseWritable
    VfsTreeProducer = VfsTreeProducerWritable
    TelegramClient = Client

    extensions = [TgmountExtensionWritable()]

    def __init__(self, storage: MockedTelegramStorage) -> None:
        logger.debug("MockedTgmountBuilderBaseWritable()")
        super().__init__(storage)


class TgmountIntegrationContextWritable(TgmountIntegrationContext):
    MockedTgmountBuilderBase = MockedTgmountBuilderBaseWritable
    # MockedClientWriter = Client

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
        tgm: TgmountBaseWritable = ctx.shared["tgm"]

        msg1 = await source1.message("text message 1")
        assert await ctx.listdir("/") == ["1_message.txt"]

        async with await ctx.open("/file2.txt", "w") as f:
            await f.write("HELLO")

        assert await ctx.read_text("/2_file2.txt") == "HELLO"
        # tgm.vfs_tree.

    await ctx.run_test(test, cfg_or_root=config)
