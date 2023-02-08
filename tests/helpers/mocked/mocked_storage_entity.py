from collections.abc import Mapping

import telethon
from tests.helpers.mocked.types import EntityId, MockedStorageProto

from tgmount import tglog

from tgmount.tgclient.message_types import DocumentProto, PhotoProto
from tgmount.tgclient.types import (
    DocId,
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    TotalListTyped,
)
from tgmount.util import none_fallback, random_int, yes

from .mocked_message import (
    MockedDocument,
    MockedFile,
    MockedForward,
    MockedMessage,
    MockedMessageWithDocument,
    MockedMessageWithPhoto,
    MockedPhoto,
    MockedReactions,
    MockedSender,
)


def random_file_reference() -> bytes:
    return bytes([random_int(255)() for _ in range(0, 32)])


def get_entity_chat_id(ent: EntityId):
    return hash(ent)


class StorageEntityBase:
    def __init__(self, storage: MockedStorageProto, entity: EntityId) -> None:
        self._entity_id = entity
        self._storage: MockedStorageProto = storage
        self._messages: list[MockedMessage] = []
        self._chat_id = get_entity_chat_id(entity)

        self._last_message_id = 0

    @property
    def entity_id(self):
        return self._entity_id

    @property
    def chat_id(self):
        return self._chat_id

    def init_message(self):
        return MockedMessage(chat_id=self.chat_id)

    def get_new_message_id(self):
        self._last_message_id += 1
        return self._last_message_id

    async def _edit_message(
        self, old_message: MockedMessage, message: MockedMessage
    ) -> MockedMessage:
        self._messages = list(filter(lambda m: m.id != old_message.id, self._messages))

        self._messages.append(message)

        return message

    async def add_message(self, message: MockedMessage) -> MockedMessage:
        message.id = self.get_new_message_id()
        message.chat_id = self.chat_id
        self._messages.append(message)

        return message

    async def delete_messages(self, message_ids: list[int]):
        entity_messages = []

        for msg in self._messages:
            if msg.id in message_ids:
                continue
            entity_messages.append(msg)

        self._messages = entity_messages

    @property
    def messages(self) -> TotalListTyped[MockedMessage]:
        msgs = []
        for m in self._messages:
            if yes(m.document):
                m.document = self._storage.get_storage_document(
                    m.document.id
                ).get_document()
            elif yes(m.photo):
                m.photo = self._storage.get_storage_photo(m.photo.id).get_photo()

        return TotalListTyped(
            sorted(
                [m.clone() for m in self._messages],
                key=lambda m: m.id,
            )
        )

    def get_messages(
        self, ids: list[int] | None = None
    ) -> TotalListTyped[MockedMessage]:
        if yes(ids):
            return TotalListTyped([m for m in self.messages if m.id in ids])

        return self.messages

    async def text_messages(self, texts: list[str]) -> list[MockedMessage]:
        res = []
        for text in texts:
            res.append(await self.message(text=text))
        return res

    async def edit_message(
        self, old_message: MockedMessage, new_message: MockedMessage
    ):
        return await self._storage.edit_message(old_message, new_message)

    async def message(
        self,
        text: str | None = None,
        put=True,
        sender: str | MockedSender | None = None,
        forward: str | MockedForward | None = None,
        reactions: Mapping[str, int] | None = None,
    ) -> MockedMessage:
        msg = self.init_message()

        if sender is not None:
            msg.sender = (
                MockedSender(username=sender, id=None)
                if isinstance(sender, str)
                else sender
            )
            msg.from_id = msg.sender.id

        if forward is not None:
            if isinstance(forward, MockedForward):
                msg.forward = forward
            else:
                msg.forward = MockedForward.create(None, forward)

        if text is not None:
            msg.text = text

        if reactions is not None:
            msg.reactions = MockedReactions.from_dict(reactions)

        if put:
            await self._storage.put_message(msg)

        return msg

    async def photo(
        self,
        file: str,
        *,
        text: str | None = None,
        sender: str | MockedSender | None = None,
        msg_id: int | None = None,
        reactions: Mapping[str, int] | None = None,
        forward: str | MockedForward | None = None,
        put=True,
    ) -> MockedMessageWithPhoto:
        msg = await self.message(
            put=False,
            sender=sender,
            forward=forward,
            reactions=reactions,
        )

        if yes(msg_id):
            msg.id = msg_id

        storage_file = await self._storage.create_storage_photo(file)
        msg.file = MockedFile.from_photo(storage_file.get_photo())
        msg.text = text
        msg.photo = storage_file.get_photo()

        if put:
            await self._storage.put_message(msg)

        return msg

    async def document(
        self,
        file: str | DocumentProto | bytes,
        *,
        sender: str | MockedSender | None = None,
        forward: str | MockedForward | None = None,
        file_name: str | bool = True,
        text: str | None = None,
        audio=False,
        image=False,
        video=False,
        put=True,
        voice_note=False,
        video_note=False,
        gif=False,
        reactions: Mapping[str, int] | None = None,
        msg_id: int | None = None,
    ) -> MockedMessageWithDocument:
        msg = await self.message(
            put=False,
            sender=sender,
            forward=forward,
            reactions=reactions,
        )

        if yes(msg_id):
            msg.id = msg_id

        if isinstance(file, (str, bytes)):
            storage_file = await self._storage.create_storage_document(file, file_name)
            if image:
                storage_file.attributes.append(
                    telethon.types.DocumentAttributeImageSize(100, 100)
                )

            msg.document = storage_file.get_document()
        # elif isinstance(file, bytes):
        #     pass
        else:
            storage_file = self._storage.get_storage_document(file.id)

            msg.document = file

        msg.text = text
        msg.file = MockedFile.from_filename(storage_file.name)

        if audio:
            msg.audio = msg.document

        if gif:
            msg.gif = msg.document

        if video:
            msg.video = msg.document

        if voice_note:
            msg.voice = msg.document

        if video_note:
            msg.video_note = msg.document

        if put:
            await self._storage.put_message(msg)

        return msg

    async def audio_file_message(
        self,
        file: str,
        performer: str | None,
        title: str | None,
        duration: int,
        text: str | None = None,
        file_name: str | bool = True,
        sender: str | MockedSender | None = None,
        put=True,
    ):
        msg = await self.document(
            file, file_name=file_name, text=text, audio=True, sender=sender, put=False
        )
        msg.file.performer = performer
        msg.file.title = title
        msg.file.duration = duration

        if put:
            await self._storage.put_message(msg)

        return msg


class StorageEntity(StorageEntityBase):
    pass
