import logging
from typing import Any, TypeVar

# import telethon
from telethon.errors import FileReferenceExpiredError
from tgmount import tgclient, vfs
from tgmount.tgclient.message_types import MessageProto, PhotoProto
from tgmount.tgmount.error import TgmountError
from tgmount.util import none_fallback

from .guards import MessageDownloadable, MessageWithCompressedPhoto
from .source.document import SourceItemDocument
from .source.item import FileSourceItem
from .source.photo import SourceItemPhoto
from .source.types import InputSourceItem
from .source.util import BLOCK_SIZE, split_range
from .types import TypeInputFileLocation

logger = logging.getLogger("tgclient")

T = TypeVar("T")

# XXX telethon.utils.get_input_document
# XXX telethon.utils.get_input_photo
# XXX telethon.utils.get_input_media
# XXX telethon.utils.get_message_id
# XXX telethon.utils.get_input_location
# XXX telethon.utils.is_video
# XXX telethon.utils.is_audio
# XXX telethon.utils.is_gif


def item_to_inner_object(input_item: InputSourceItem) -> FileSourceItem:
    if PhotoProto.guard(input_item):
        item = SourceItemPhoto(input_item)
    else:
        item = SourceItemDocument(input_item)

    return item


def get_filesource_item(message: MessageDownloadable) -> FileSourceItem:
    if MessageWithCompressedPhoto.guard(message):
        return item_to_inner_object(message.photo)

    if message.document is not None:
        return item_to_inner_object(message.document)

    raise ValueError(f"message {message} is not downloadable")


class TelegramFilesSource:
    """Class that provides file content for a `MessageDownloadable`"""

    def __init__(
        self,
        client: tgclient.client_types.TgmountTelegramClientReaderProto,
        request_size: int | None = None,
    ) -> None:
        self.client = client
        self.items_file_references: dict[int, bytes] = {}
        self.request_size = none_fallback(request_size, BLOCK_SIZE)

    def file_content(self, message: MessageDownloadable) -> vfs.FileContent:

        item = get_filesource_item(message)

        async def read_func(handle: Any, off: int, size: int) -> bytes:
            return await self.read(message, off, size)

        fc = vfs.FileContent(size=item.size, read_func=read_func)

        return fc

    async def read(
        self, message: MessageDownloadable, offset: int, limit: int
    ) -> bytes:

        return await self._item_read_function(message, offset, limit)

    async def _get_item_input_location(
        self, item: FileSourceItem
    ) -> TypeInputFileLocation:
        return item.input_location(
            self._get_item_file_reference(item),
        )

    def _get_item_file_reference(self, item: FileSourceItem) -> bytes:
        return self.items_file_references.get(
            item.id,
            item.file_reference,
        )

    def _set_item_file_reference(self, item: FileSourceItem, file_reference: bytes):
        self.items_file_references[item.id] = file_reference

    async def _update_item_file_reference(
        self, message: MessageDownloadable
    ) -> TypeInputFileLocation:

        item = get_filesource_item(message)

        refetched_msg: MessageProto

        [refetched_msg] = await self.client.get_messages(
            message.chat_id, ids=[message.id]
        )

        if not MessageDownloadable.guard(message):
            logger.error(f"refetched_msg isnt a Message")
            logger.error(f"refetched_msg={refetched_msg}")
            raise TgmountError(f"refetched_msg isnt a Message")
            # XXX what should i do if refetched_msg is None

        # XXX handle photo
        if refetched_msg.document is None:
            # if refetched_msg.document is None:
            raise ValueError(f"missing document")

        self._set_item_file_reference(item, refetched_msg.document.file_reference)

        return await self._get_item_input_location(item)

    async def _retrieve_file_chunk(
        self,
        input_location: TypeInputFileLocation,
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

        # request_size = (
        #     request_size
        #     if (offset + request_size) <= document_size
        #     else document_size - offset
        # )

        # if offset + request_size > document_size:
        #     offset = document_size - 0

        async for chunk in self.client.iter_download(
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
        # item: SourceItem,
        offset: int,
        limit: int,
    ) -> bytes:
        item = get_filesource_item(message)

        logger.debug(
            f"TelegramFilesSource._item_read_function(Message(id={message.id},chat_id={message.chat_id}), item(name={message.file.name}, id={item.id}, offset={offset}, limit={limit})"  # type: ignore
        )

        input_location = await self._get_item_input_location(item)

        try:
            chunk = await self._retrieve_file_chunk(
                input_location,
                offset,
                limit,
                item.size,
                request_size=self.request_size,
            )
        except FileReferenceExpiredError:
            logger.debug(
                f"FileReferenceExpiredError was caught. file_reference for msg={item.id} needs refetching"
            )

            input_location = await self._update_item_file_reference(message)

            chunk = await self._retrieve_file_chunk(
                input_location,
                offset,
                limit,
                item.size,
                request_size=self.request_size,
            )

        logger.debug(
            f"TelegramFilesSource.document_read_function() = {len(chunk)} bytes"
        )
        return chunk


""" 
https://core.telegram.org/api/files
"""
