from tgmount.common.subscribable import Subscribable
from tgmount.tgclient.guards import MessageDownloadable
from .logger import logger
from tgmount.tgclient.client_types import (
    TgmountTelegramClientSendFileProto,
    TgmountTelegramClientWriterProto,
)
from tgmount.tgclient.types import EntityId
from tgmount.util import map_none
from telethon import types
import functools


class TelegramFileUploader(Subscribable):
    logger = logger.getChild("TelegramFileUploader")

    def __init__(
        self, client: TgmountTelegramClientWriterProto, entity: EntityId
    ) -> None:
        super().__init__()

        self._entity = entity
        self._client = client
        self._logger = TelegramFileUploader.logger.getChild(
            str(entity), suffix_as_tag=True
        )

    def progress_callback(self, file_name, uploaded: int, total: int):
        self._logger.debug(f"{file_name} uploaded {int((uploaded/total)*100)}%")

    async def remove(self, message_ids: list[int]):
        await self._client.delete_messages(self._entity, message_ids=message_ids)

    async def upload(
        self,
        file: bytes,
        # part_size_kb: float | None = None,
        file_size: int | None = None,
        file_name: str | None = None,
    ) -> MessageDownloadable:
        self._logger.debug(f"Uploading {file_name} of {file_size} bytes")

        msg = await self._client.send_file(
            self._entity,
            file,
            force_document=True,
            file_size=file_size,
            attributes=map_none(
                file_name,
                lambda file_name: [types.DocumentAttributeFilename(file_name)],
            ),
            progress_callback=functools.partial(self.progress_callback, file_name)
            # file_name=file_name,
        )
        await self.notify(msg)
        return msg
