import os
from collections import defaultdict

import aiofiles
from telethon import events
from telethon.errors import FileReferenceExpiredError

from tests.helpers.mocked.mocked_storage_files_document import (
    StorageItemDocument,
)
from tests.helpers.mocked.mocked_storage_files_photo import StorageItemPhoto
from tgmount import tglog
from tgmount.tgclient import (
    IterDownloadProto,
    ListenerEditedMessage,
    ListenerNewMessages,
    ListenerRemovedMessages,
)
from tgmount.tgclient.types import (
    DocId,
    InputDocumentFileLocation,
    InputPhotoFileLocation,
    TotalListTyped,
)
from tgmount.util import none_fallback, yes

from .mocked_message import MockedMessage
from .mocked_storage_entity import StorageEntity, get_entity_chat_id
from .mocked_storage_files import StorageFiles
from .types import EntityId, MockedStorageProto

from .util import random_int


class MockedTelegramStorage(MockedStorageProto):
    _logger = tglog.getLogger("MockedTelegramStorage()")

    @staticmethod
    def create_from_entities_list(
        entities: list[str],
    ) -> tuple["MockedTelegramStorage", list[StorageEntity]]:
        storage = MockedTelegramStorage()
        es = []
        for ent_id in entities:
            es.append(storage.create_entity(ent_id))

        return (storage, es)

    def __init__(self, entities: list[str] | None = None) -> None:
        self._entities: dict[EntityId, StorageEntity] = {}
        self._entity_by_chat_id: dict[int, StorageEntity] = {}

        self._files_cache: dict[str, bytes] = {}
        self._files = StorageFiles()

        self._subscriber_per_entity_new: defaultdict[
            EntityId, list[ListenerNewMessages]
        ] = defaultdict(list)

        self._subscriber_per_entity_removed: defaultdict[
            EntityId, list[ListenerRemovedMessages]
        ] = defaultdict(list)

        self._subscriber_per_entity_edited: defaultdict[
            EntityId, list[ListenerEditedMessage]
        ] = defaultdict(list)

        for entity_id in none_fallback(entities, []):
            self.create_entity(entity_id)

    @property
    def files(self):
        return self._files

    def _create_entity(self, entity: EntityId) -> StorageEntity:
        return StorageEntity(self, entity)

    def create_entity(self, entity: EntityId) -> StorageEntity:
        if entity not in self._entities:
            self._entities[entity] = self._create_entity(entity)
            self._entity_by_chat_id[get_entity_chat_id(entity)] = self._entities[entity]

        return self._entities[entity]

    def get_entity(self, entity_id: str | int) -> StorageEntity:
        entity = None

        if isinstance(entity_id, str):
            entity = self._entities.get(entity_id)

        if isinstance(entity_id, int):
            entity = self._entity_by_chat_id.get(entity_id)

        if not yes(entity):
            raise ValueError(f"Missing {entity_id}")

        return entity

    def subscribe_new_messages(self, listener: ListenerNewMessages, chats):
        self._subscriber_per_entity_new[chats].append(listener)

    def subscribe_removed_messages(self, listener: ListenerRemovedMessages, chats):
        self._subscriber_per_entity_removed[chats].append(listener)

    def subscribe_edited_message(self, listener: ListenerEditedMessage, chats):
        self._subscriber_per_entity_edited[chats].append(listener)

    async def _read_file(self, file_path: str) -> bytes:
        if file_path in self._files_cache:
            return self._files_cache[file_path]

        async with aiofiles.open(file=file_path, mode="rb") as f:
            self._files_cache[file_path] = await f.read()
            return self._files_cache[file_path]

    async def _add_file(self, file_bytes: bytes, file_name: str):
        return self._files.add_document(file_bytes=file_bytes, file_name=file_name)

    async def create_storage_document(
        self,
        file: str | bytes,
        file_name: str | bool = True,
    ) -> StorageItemDocument:
        if isinstance(file, str):
            file_bytes = await self._read_file(file)
        else:
            file_bytes = file

        if isinstance(file_name, bool) and file_name is True:
            if isinstance(file, str):
                _file_name = os.path.basename(file)
            else:
                _file_name = str(random_int(1000000))
        elif isinstance(file_name, bool) and file_name is False:
            _file_name = None
        else:
            _file_name = file_name

        storage_file = self._files.add_document(
            file_bytes,
            file_name=_file_name,
        )

        return storage_file

    def get_storage_document(self, doc_id: DocId) -> StorageItemDocument:
        return self._files.get_document(doc_id)

    def get_storage_photo(self, doc_id: DocId) -> StorageItemPhoto:
        return self._files.get_photo(doc_id)

    async def create_storage_photo(
        self,
        file: str,
    ) -> StorageItemPhoto:
        file_bytes = await self._read_file(file)

        photo = self._files.add_photo(
            file_bytes,
        )

        return photo

    def get_entity_by_chat_id(self, chat_id: int) -> StorageEntity:
        return self._entity_by_chat_id[chat_id]

    async def edit_message(
        self, old_message: MockedMessage, new_message: MockedMessage
    ):
        ent = self.get_entity_by_chat_id(old_message.chat_id)
        message = await ent._edit_message(old_message, new_message)

        for s in self._subscriber_per_entity_edited[ent.entity_id]:
            await s(events.MessageEdited.Event(message))

        return message

    async def put_message(self, message: MockedMessage, notify=True):
        ent = self._entity_by_chat_id[message.chat_id]

        message = await ent.add_message(message)

        if notify:
            for s in self._subscriber_per_entity_new[ent.entity_id]:
                await s(events.NewMessage.Event(message))

        return message

    async def delete_messages(
        self, entity_id: EntityId, message_ids: list[int], notify=True
    ):
        ent = self.get_entity(entity_id)
        await ent.delete_messages(message_ids)

        if notify:
            for s in self._subscriber_per_entity_removed[entity_id]:
                await s(events.MessageDeleted.Event(message_ids, entity_id))

    async def get_messages(
        self, entity_or_chat_id: int | str, ids: list[int] | None = None
    ) -> TotalListTyped:
        ent = self.get_entity(entity_or_chat_id)

        return ent.get_messages(ids)

    def set_file_reference(self, doc_id: DocId, new_file_reference: bytes):
        file = self._files.get_item(doc_id)

        if file is None:
            raise Exception(f"Missing file with id {doc_id}")

        file.file_reference = new_file_reference
        # new_file = file.clone()
        # new_file.file_reference = new_file_reference

        # self._files.put_file(new_file)

    def iter_download(
        self,
        *,
        input_location: InputPhotoFileLocation | InputDocumentFileLocation,
        offset: int,
        request_size: int,
        limit: int,
        file_size: int,
    ) -> IterDownloadProto:
        file = self._files.get_item(input_location.id)

        if file is None:
            raise Exception(f"Missing file with id {input_location.id}")

        if file.file_reference != input_location.file_reference:
            raise FileReferenceExpiredError(None)

        self._logger.debug(
            f"iter_download({file.id}, size={file._size}, offset={offset}, limit={limit})"
        )

        file_bytes = file.file_bytes
        _range = file_bytes[offset : offset + limit * request_size]
        # _range = file_bytes[offset : offset + limit * request_size]
        chunks = []

        while len(_range):
            chunks.append(_range[:request_size])
            _range = _range[request_size:]

        return IterDownload(chunks)


class IterDownload(IterDownloadProto):
    def __init__(self, chunks: list[bytes]) -> None:
        self._iter = iter(chunks)

    def __aiter__(self) -> "IterDownloadProto":
        return self

    async def __anext__(self) -> bytes:
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration
