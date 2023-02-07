from abc import abstractmethod
import logging
from re import L
from typing import Awaitable, Callable, Optional
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
from tgmount.tgclient.client_types import TgmountTelegramClientSendFileProto
from tgmount.tgclient.events_disptacher import EntityId
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir, VfsTreeDirContent
from tgmount.util import map_none
from tgmount.vfs.types.dir import DirContentWritableProto
from tgmount.vfs.types.file import FileContentWritableProto, FileLike
from tgmount.fs.writable import FileSystemOperationsWritable
from telethon import types

from .fixtures import *
from ..logger import logger


class TelegramFileUploader:
    logger = logger.getChild("TelegramFileUploader")

    def __init__(
        self, client: TgmountTelegramClientSendFileProto, entity: EntityId
    ) -> None:
        self._entity = entity
        self._client = client
        self._logger = TelegramFileUploader.logger.getChild(
            str(entity), suffix_as_tag=True
        )

    async def upload(
        self,
        file: bytes,
        # part_size_kb: float | None = None,
        file_size: int | None = None,
        file_name: str | None = None,
    ):
        self._logger.debug(f"Uploading {file_name} of {file_size} bytes")
        await self._client.send_file(
            self._entity,
            file,
            force_document=True,
            file_size=file_size,
            attributes=map_none(
                file_name,
                lambda file_name: [types.DocumentAttributeFilename(file_name)],
            )
            # file_name=file_name,
        )


def bytearray_write(target: bytearray, offset: int, buf: bytes):
    target_len = len(target)

    for idx, b in enumerate(buf):
        if offset + idx >= target_len:
            target.append(b)
        else:
            target[offset + idx] = b


class FileContentWritableConsumer(FileContentWritableProto):
    """Consumes all the bytes. The result will be available in `close_func`"""

    size: int

    def __init__(self) -> None:
        self._data: bytearray = bytearray()
        # self._consumed = False

    async def seek_func(self, handle, n: int, w: int):
        raise NotImplementedError()

    async def read_func(self, handle, off: int, size: int) -> bytes:
        raise NotImplementedError()

    tell_func: Optional[Callable[[Any], Awaitable[int]]] = None

    async def write(self, handle: None, off: int, buf: bytes):
        bytearray_write(self._data, off, buf)
        self.size = len(self._data)

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
        await self._uploader.upload(self._data)


class TgmountBaseWritable(TgmountBase):
    FileSystemOperations = FileSystemOperationsWritable

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        logger.debug("TgmountBaseWritable()")


class VfsTreeDirContentWritable(VfsTreeDirContent, DirContentWritableProto):
    def __init__(self, tree: "VfsTree", path: str) -> None:
        super().__init__(tree, path)

    async def create(self, filename: str) -> FileLike:
        logger.debug(f"VfsTreeDirContentWritable.create({filename})")
        thedir = await self._tree.get_dir(self._path)

        filelike = vfs.FileLike(
            filename,
            content=FileContentWritableUpload(uploader, filename),
            writable=True,
        )

        return filelike


class VfsTreeDirWritable(VfsTreeDir):
    def __init__(self, tree: "VfsTree", path: str, wrappers=None) -> None:
        super().__init__(tree, path, wrappers)


class VfsTreeWritable(VfsTree):
    VfsTreeDirContent = VfsTreeDirContentWritable
    VfsTreeDir = VfsTreeDirWritable

    def __init__(self) -> None:
        logger.debug("VfsTreeWritable()")
        super().__init__()


class MockedTgmountBuilderBaseWritable(MockedTgmountBuilderBase):
    VfsTree = VfsTreeWritable
    TgmountBase = TgmountBaseWritable

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
        root={"source": "source1"},
    )

    async def test():
        fs: FileSystemOperationsWritable = ctx.shared["fs"]
        tgm: TgmountBaseWritable = ctx.shared["tgm"]

        msg1 = await source1.message("text message 1")
        assert await ctx.listdir("/") == ["1_message.txt"]

        async with await ctx.open("/file2.txt", "w") as f:
            await f.write("HELLO")

        assert await ctx.read_text("/file2.txt") == "HELLO"
        # tgm.vfs_tree.

    await ctx.run_test(test, cfg_or_root=config)
