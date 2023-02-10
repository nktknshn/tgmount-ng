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


class TelegramFileUploader:
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

        self._progress: dict[
            str, tuple[int, int, Exception | MessageDownloadable | None]
        ] = {}

        self.on_uploaded: Subscribable[MessageDownloadable] = Subscribable()
        self.on_error: Subscribable[Exception] = Subscribable()

        # TODO cancel upload tasks

    @property
    def progress(self):
        return self._progress

    def progress_callback(self, file_name: str, uploaded: int, total: int):
        self._logger.debug(f"{file_name} uploaded {int((uploaded/total)*100)}%")
        self._progress[file_name] = (uploaded, total, None)

    async def remove(self, message_ids: list[int]):
        self._logger.debug(f"Remove: {message_ids}")

        return await self._client.delete_messages(
            self._entity,
            message_ids=message_ids,
        )

    async def text_message(self, text: str):
        return await self._client.send_message(self._entity, text)

    async def upload(
        self, file_bytes: bytes, file_size: int, file_name: str
    ) -> MessageDownloadable:
        self._logger.debug(f"Uploading {file_name} of {file_size} bytes")

        self._progress[file_name] = (0, file_size, None)

        try:
            msg = await self._client.send_file(
                self._entity,
                file_bytes,
                force_document=True,
                file_size=file_size,
                attributes=map_none(
                    file_name,
                    lambda file_name: [types.DocumentAttributeFilename(file_name)],
                ),
                progress_callback=functools.partial(self.progress_callback, file_name),
            )

            self._progress[file_name] = (file_size, file_size, msg)

            self._logger.debug(f"Uploaded {file_name}.")

            await self.on_uploaded.notify(msg)

            return msg
        except Exception as e:
            self._logger.error(f"Error while uploading {file_name}: {e}")
            (t, p, _) = self._progress[file_name]
            self._progress[file_name] = (t, p, e)
            await self.on_error.notify(e)
            raise e
