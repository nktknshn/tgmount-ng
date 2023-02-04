import logging
from typing import Any, TypeVar

from random import random

# import telethon
from telethon.errors import FileReferenceExpiredError
from tgmount import tgclient, vfs
from tgmount.tgclient.message_types import DocumentProto, MessageProto, PhotoProto
from tgmount.error import TgmountError
from tgmount.util import none_fallback

from .guards import MessageDownloadable, MessageWithCompressedPhoto, MessageWithDocument
from .source.document import SourceItemDocument
from .source.item import FileSourceItem, InputLocation
from .source.photo import SourceItemPhoto
from .source.types import InputSourceItem
from .source.util import BLOCK_SIZE, split_range
from .types import (
    DocId,
    InputDocumentFileLocation,
    InputPhotoFileLocation,
)


logger = logging.getLogger("tgclient")

T = TypeVar("T")


class FilesSourceError(TgmountError):
    pass


def get_message_downloadable_size(message: MessageDownloadable):
    if MessageWithCompressedPhoto.guard(message):
        return SourceItemPhoto(message.photo).size

    if MessageWithDocument.guard(message):
        return SourceItemDocument(message.document).size

    raise ValueError(f"Message {message} is not downloadable")


class TelegramFilesSource:
    """Class that provides file content for a `MessageDownloadable`"""

    def __init__(
        self,
        client: tgclient.client_types.TgmountTelegramClientReaderProto,
        request_size: int | None = None,
    ) -> None:
        self._client = client
        self._items_file_references: dict[DocId, bytes] = {}
        self._request_size = none_fallback(request_size, BLOCK_SIZE)

    def get_filesource_item(self, message: MessageDownloadable) -> FileSourceItem:
        if MessageWithCompressedPhoto.guard(message):
            return SourceItemPhoto(message.photo)

        if MessageWithDocument.guard(message):
            return SourceItemDocument(message.document)

        raise ValueError(f"Message {message} is not downloadable")

    def file_content(self, message: MessageDownloadable) -> vfs.FileContent:

        item = self.get_filesource_item(message)

        async def read_func(handle: Any, off: int, size: int) -> bytes:
            return await self.read(message, off, size)

        fc = vfs.FileContent(size=item.size, read_func=read_func)

        return fc

    async def read(
        self, message: MessageDownloadable, offset: int, limit: int
    ) -> bytes:

        return await self._item_read_function(message, offset, limit)

    async def _get_item_input_location(self, item: FileSourceItem) -> InputLocation:
        return item.input_location(
            self._get_item_file_reference(item),
        )

    def _get_item_file_reference(self, item: FileSourceItem) -> bytes:
        return self._items_file_references.get(
            item.id,
            item.file_reference,
        )

    def _set_item_file_reference(self, item: FileSourceItem, file_reference: bytes):
        self._items_file_references[item.id] = file_reference

    async def _refetch_item_file_reference(
        self, message: MessageDownloadable
    ) -> InputLocation:

        item = self.get_filesource_item(message)

        refetched_msg: MessageProto

        [refetched_msg] = await self._client.get_messages(
            message.chat_id, ids=[message.id]
        )

        # logger.debug(f"Refetched message: {refetched_msg}")
        # logger.debug(f"Refetched message: {refetched_msg.document.file_reference}")

        if not MessageDownloadable.guard(message):
            logger.error(f"refetched_msg isn't a MessageDownloadable")
            logger.error(f"refetched_msg={refetched_msg}")
            raise FilesSourceError(f"refetched_msg isn't a MessageDownloadable")
            # XXX what should i do if refetched_msg is None or the document was
            # removed from the message

        item = self.get_filesource_item(message)

        self._set_item_file_reference(item, item.file_reference)

        return await self._get_item_input_location(item)

    async def _retrieve_file_chunk(
        self,
        input_location: InputDocumentFileLocation | InputPhotoFileLocation,
        offset: int,
        limit: int,
        document_size: int,
        *,
        request_size=BLOCK_SIZE,
    ) -> bytes:

        # XXX adjust request_size
        ranges = split_range(offset, limit, request_size)
        result = bytes()

        # if random() > 0.9:
        #     raise FileReferenceExpiredError(None)

        async for chunk in self._client.iter_download(
            input_location,
            offset=ranges[0],
            request_size=request_size,
            limit=len(ranges) - 1,
            file_size=document_size,
        ):
            logger.debug(f"chunk = {len(chunk)} bytes")
            result += chunk

        return result[offset - ranges[0] : offset - ranges[0] + limit]

    async def _item_read_function(
        self,
        message: MessageDownloadable,
        offset: int,
        limit: int,
    ) -> bytes:
        item = self.get_filesource_item(message)

        logger.debug(
            f"TelegramFilesSource._item_read_function(Message(id={message.id},chat_id={message.chat_id}), item(name={message.file.name}, id={item.id}, offset={offset}, limit={limit})"
        )

        input_location = await self._get_item_input_location(item)

        try:
            chunk = await self._retrieve_file_chunk(
                input_location,
                offset,
                limit,
                item.size,
                request_size=self._request_size,
            )
        except FileReferenceExpiredError:
            logger.warning(
                f"FileReferenceExpiredError was caught. file_reference for msg={item.id} needs refetching"
            )

            input_location = await self._refetch_item_file_reference(message)

            chunk = await self._retrieve_file_chunk(
                input_location,
                offset,
                limit,
                item.size,
                request_size=self._request_size,
            )

        logger.debug(
            f"TelegramFilesSource.document_read_function() = {len(chunk)} bytes"
        )
        return chunk


""" 
https://core.telegram.org/api/files
"""
