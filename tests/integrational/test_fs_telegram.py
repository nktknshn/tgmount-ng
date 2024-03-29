import asyncio
import io
import logging
import os

import aiofiles as af
import pytest
import pytest_asyncio
import telethon
import tgmount.tgclient as tg
import tgmount.vfs as vfs
import tgmount.zip as z
import tgmount.fs as fs

from tgmount.tglog import init_logging
from tgmount.tgclient.files_source import TelegramFilesSource
from tgmount.vfs import DirContentSourceMapping
from tgmount.tgclient import guards

from ..helpers.fixtures_common import mnt_dir
from ..helpers.tgclient import get_client_with_source
from ..helpers.spawn import spawn_fs_ops

Message = telethon.tl.custom.Message
Document = telethon.types.Document

InputMessagesFilterDocument = telethon.tl.types.InputMessagesFilterDocument


async def messages_to_files_tree(
    source: TelegramFilesSource,
    messages: list[telethon.tl.custom.Message],
) -> DirContentSourceMapping:
    return dict(
        [
            (
                msg.file.name,
                source.file_content(msg),
            )
            for msg in messages
            if msg.file.name is not None and guards.MessageDownloadable.guard(msg)
        ]
    )


async def main_test1(props, _):
    init_logging(props["debug"])

    client, storage = await get_client_with_source()
    messages = await client.get_messages(
        "tgmounttestingchannel",
        limit=3,
        reverse=True,
        filter=InputMessagesFilterDocument,
    )

    return fs.FileSystemOperations(
        vfs.root({"tmtc": await messages_to_files_tree(storage, messages)})
    )


@pytest.mark.asyncio
async def _test_fs_tg_test1(mnt_dir, caplog):
    caplog.set_level(logging.DEBUG)

    amount = 512 * 1024

    f = await af.open("tests/fixtures/bandcamp1.zip", "rb")
    bc1 = await f.read1(amount)

    for m in spawn_fs_ops(main_test1, {"debug": False}, mnt_dir=mnt_dir, min_tasks=10):
        subfiles = os.listdir(m.path("tmtc/"))
        assert len(subfiles) == 3

        fopen1 = lambda: af.open(m.path("tmtc/bandcamp1.zip"), "rb")
        fopen2 = lambda: af.open(m.path("tmtc/linux_zip_stored1.zip"), "rb")

        async def read(f, amount, msg, offset=None):
            if offset is not None:
                await f.seek(offset)

            print(f"reading {msg} {amount}")
            res = await f.read(amount)
            print(f"done reading {msg} {amount}")
            return res

        [f1, f2, f3, f4, f5, f6] = await asyncio.gather(
            fopen1(), fopen1(), fopen1(), fopen2(), fopen2(), fopen2()
        )

        [r1, r2, r3, r4, r5, r6] = await asyncio.gather(
            read(f1, amount, "f1"),
            read(f2, amount, "f2"),
            read(f3, amount * 2, "f3", 30000),
            read(f4, amount, "f4"),
            read(f5, amount, "f5"),
            read(f6, amount * 2, "f6", 30000),
        )

        assert bc1 == r1
        assert bc1 == r2


class TrackingSource(TelegramFilesSource):
    def __init__(
        self, client: tg.TgmountTelegramClient, request_size: int = 128 * 1024
    ) -> None:
        super().__init__(client, request_size)

        self.total_asked = 0

    async def item_read_function(
        self, message: Message, item: Document, offset: int, limit: int
    ) -> bytes:
        self.total_asked += limit

        if limit > 2187200:
            pass

        print(f"offset={offset} limit={limit}")
        print(f"self.total_asked = {self.total_asked}")
        return await super().read(message, offset, limit)
