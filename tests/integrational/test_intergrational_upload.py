from abc import abstractmethod
import asyncio
import functools
import logging
import pytest
from tests.helpers.mocked.mocked_client import MockedClientReader, MockedClientWriter

from tests.helpers.mocked.mocked_storage import MockedTelegramStorage
from tests.integrational.integrational_test import MockedTgmountBuilderBase

from tests.helpers.config import create_config
from tgmount.config.config import DirConfigReader
from tgmount.tgmount.extensions.writable import (
    TgmountExtensionWritable,
)
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.util.col import bytearray_write
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
    TelegramClient = Client

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
        root={
            "source": "source1",
            "upload": True,
            "sysinfo": {"producer": "SysInfo", "source": "source1"},
        },
        extensions={
            DirConfigReader: [TgmountExtensionWritable()],
        },
    )

    async def test():
        fs: FileSystemOperationsWritable = ctx.shared["fs"]
        tgm: TgmountBase = ctx.shared["tgm"]

        await source1.message("text message")
        assert await ctx.listdir_set("/") == set(["1_message.txt", "sysinfo"])

        # upload happens on file close
        async with await ctx.open("/file2.txt", "w") as f:
            await f.write("HELLO")

        assert await ctx.read_text("/2_file2.txt") == "HELLO"

        assert await ctx.listdir_set("/") == set(
            ["1_message.txt", "2_file2.txt", "sysinfo"]
        )

        await ctx.remove("/2_file2.txt")

        assert await ctx.listdir_set("/") == set(["1_message.txt", "sysinfo"])

        print(await ctx.read_text("/sysinfo/uploaders"))

    await ctx.run_test(test, cfg_or_root=config)
