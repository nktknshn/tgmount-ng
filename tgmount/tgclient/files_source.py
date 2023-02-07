import logging
from typing import Any, TypeGuard, TypeVar

from telethon.errors import FileReferenceExpiredError, FileReferenceInvalidError
from tgmount import tgclient, vfs
from tgmount.tgclient.message_types import MessageProto
from tgmount.error import TgmountError
from tgmount.util import none_fallback

from .guards import MessageDownloadable, MessageWithCompressedPhoto, MessageWithDocument
from .source.document import SourceItemDocument
from .source.item import FileSourceItem, InputLocation
from .source.photo import SourceItemPhoto
from .source.util import BLOCK_SIZE, split_range
from .types import (
    DocId,
    InputDocumentFileLocation,
    InputPhotoFileLocation,
)
from .logger import logger as module_logger

# logger = logging.getLogger("tgclient")

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

    logger = module_logger.getChild(f"TelegramFilesSource")

    def __init__(
        self,
        client: tgclient.client_types.TgmountTelegramClientReaderProto,
        request_size: int | None = None,
    ) -> None:
        self._client = client
        self._items_file_references: dict[DocId, bytes] = {}
        self._request_size = none_fallback(request_size, BLOCK_SIZE)

    def is_message_downloadable(
        self, message: MessageProto
    ) -> TypeGuard[MessageDownloadable]:
        return MessageDownloadable.guard(message)

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

        return await self._message_read(message, offset, limit)

    async def _get_item_input_location(self, item: FileSourceItem) -> InputLocation:
        return item.input_location(
            self._get_item_file_reference(item),
        )

    def _get_item_file_reference(self, item: FileSourceItem) -> bytes:
        return self._items_file_references.get(
            item.id,
            # b"1" * 29
            item.file_reference,
        )

    def _set_item_file_reference(self, item: FileSourceItem, file_reference: bytes):
        self._items_file_references[item.id] = file_reference

    async def _refetch_message_file_reference(
        self, old_message: MessageDownloadable
    ) -> InputLocation:

        item = self.get_filesource_item(old_message)

        refetched_msg: MessageProto

        [refetched_msg] = await self._client.get_messages(
            old_message.chat_id, ids=[old_message.id]
        )

        self.logger.debug(f"Refetched message: {refetched_msg}")
        # logger.debug(f"Refetched message: {refetched_msg.document.file_reference}")

        if not self.is_message_downloadable(refetched_msg):
            self.logger.error(f"refetched_msg isn't a MessageDownloadable")
            # logger.error(f"refetched_msg={refetched_msg}")
            raise FilesSourceError(f"refetched_msg isn't a MessageDownloadable")
            # XXX what should i do if refetched_msg is None or the document was
            # removed from the message

        item = self.get_filesource_item(refetched_msg)

        self._set_item_file_reference(item, item.file_reference)

        # return await self._get_item_input_location(item)

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
            self.logger.trace(f"chunk = {len(chunk)} bytes")
            result += chunk

        return result[offset - ranges[0] : offset - ranges[0] + limit]

    async def _message_read(
        self,
        message: MessageDownloadable,
        offset: int,
        limit: int,
    ) -> bytes:
        item = self.get_filesource_item(message)

        self.logger.trace(
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
        except (FileReferenceExpiredError, FileReferenceInvalidError) as e:
            self.logger.warning(
                f"{type(e).__name__} was caught. file_reference for document={item.id} needs refetching."
            )
            self.logger.debug(f"Old file reference: {input_location.file_reference}")

            await self._refetch_message_file_reference(message)

            input_location = await self._get_item_input_location(item)

            self.logger.debug(
                f"New file reference: {self._get_item_file_reference(item)}"
            )

            chunk = await self._retrieve_file_chunk(
                input_location,
                offset,
                limit,
                item.size,
                request_size=self._request_size,
            )

        self.logger.trace(
            f"TelegramFilesSource.document_read_function() = {len(chunk)} bytes"
        )
        return chunk
