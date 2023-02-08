from .logger import logger
from tgmount.tgclient.client_types import TgmountTelegramClientSendFileProto
from tgmount.tgclient.types import EntityId
from tgmount.util import map_none
from telethon import types
import functools


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

    def progress_callback(self, file_name, uploaded: int, total: int):
        self._logger.debug(f"{file_name} uploaded {int((uploaded/total)*100)}%")

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
            ),
            progress_callback=functools.partial(self.progress_callback, file_name)
            # file_name=file_name,
        )
