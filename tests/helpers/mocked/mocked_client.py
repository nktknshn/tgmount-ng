import mimetypes
import os
import random

import asyncio
from typing import Callable
from tgmount import tglog
import tgmount.tgclient as tg
from tgmount.tgclient.client_types import (
    IterDownloadProto,
    ListenerEditedMessage,
    ListenerNewMessages,
    ListenerRemovedMessages,
    TgmountTelegramClientReaderProto,
    TgmountTelegramClientWriterProto,
)
from tgmount.tgclient.types import (
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    TotalListTyped,
)
from telethon import types

from tgmount.util import none_fallback

from .mocked_message import MockedMessage, MockedMessageWithDocument, MockedSender
from .mocked_storage import EntityId, MockedTelegramStorage

# Message = telethon.tl.custom.Message
# Document = telethon.types.Document
Client = tg.TgmountTelegramClient


class MockedClientReader(TgmountTelegramClientReaderProto):
    logger = tglog.getLogger("MockedClientReader")

    def __repr__(self) -> str:
        return f"MockedClientReader()"

    def __init__(self, storage: MockedTelegramStorage) -> None:
        self._storage = storage

    async def auth(self):
        pass

    def subscribe_new_messages(self, listener: ListenerNewMessages, chats):
        self._storage.subscribe_new_messages(listener=listener, chats=chats)

    def subscribe_removed_messages(self, listener: ListenerRemovedMessages, chats):
        self._storage.subscribe_removed_messages(listener=listener, chats=chats)

    def subscribe_edited_message(self, listener: ListenerEditedMessage, chats):
        self._storage.subscribe_edited_message(listener=listener, chats=chats)

    async def get_messages(
        self, entity: int | str, *, ids: list[int] | None = None, **kwargs
    ) -> TotalListTyped[MockedMessage]:
        await asyncio.sleep(0.1)
        return await self._storage.get_messages(entity, ids=ids)

    def iter_download(
        self,
        input_location: InputPhotoFileLocation | InputDocumentFileLocation,
        *,
        offset: int,
        request_size: int,
        limit: int,
        file_size: int,
    ) -> IterDownloadProto:
        return self._storage.iter_download(
            input_location=input_location,
            offset=offset,
            request_size=request_size,
            limit=limit,
            file_size=file_size,
        )


class MockedClientWriter(TgmountTelegramClientWriterProto):
    logger = tglog.getLogger("MockedClientWriter")

    def __init__(self, storage: MockedTelegramStorage, sender=None) -> None:
        self._storage = storage
        self._sender: MockedSender | None = sender

    def sender(self, sender: str | MockedSender):
        return MockedClientWriter(
            self._storage,
            sender if isinstance(sender, MockedSender) else MockedSender(sender, None),
        )

    async def send_message(
        self,
        entity: EntityId,
        message=None,
        file: str | None = None,
    ) -> MockedMessage:
        self.logger.info(f"send_message({entity}, {message})")
        return await self._storage.create_entity(entity).message(
            text=message,
            # file=file,
            # force_document=force_document,
        )

    async def edit_message(
        self, old_message: MockedMessage, new_message: MockedMessage
    ) -> MockedMessage:
        self.logger.info(f"edit_message({old_message}, {new_message})")
        return await self._storage.edit_message(old_message, new_message)

    async def send_file(
        self,
        entity: EntityId,
        file: str | bytes,
        *,
        caption: str | None = None,
        voice_note: bool = False,
        video_note: bool = False,
        force_document=False,
        file_size: int | None = None,
        attributes: list | None = None,
        progress_callback: Callable | None = None,
    ) -> MockedMessageWithDocument:
        video = False

        if isinstance(file, str):
            mtype = mimetypes.guess_type(file)[0]

            if mtype is not None and mtype.startswith("video") and not force_document:
                video = True
        file_name = None
        for attr in none_fallback(attributes, []):
            if isinstance(attr, types.DocumentAttributeFilename):
                file_name = attr.file_name
        return await self._storage.create_entity(entity).document(
            text=caption,
            file=file,
            voice_note=voice_note,
            video_note=video_note,
            video=video,
            sender=self._sender,
            file_name=none_fallback(file_name, False)
            # force_document=force_document,
        )

    async def delete_messages(self, entity: EntityId, *, msg_ids: list[int]):
        return await self._storage.delete_messages(entity, msg_ids=msg_ids)
