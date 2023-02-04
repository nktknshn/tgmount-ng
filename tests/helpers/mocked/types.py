from abc import abstractmethod
from typing import Protocol

from tests.helpers.mocked.mocked_storage_files_document import (
    StorageItemDocument,
)
from tests.helpers.mocked.mocked_storage_files_photo import StorageItemPhoto
from tgmount.tgclient.types import DocId
from .mocked_message import MockedMessage

EntityId = str | int


class MockedStorageProto(Protocol):
    @abstractmethod
    async def edit_message(
        self, old_message: MockedMessage, new_message: MockedMessage
    ):
        pass

    @abstractmethod
    async def put_message(self, message: MockedMessage):
        pass

    @abstractmethod
    async def delete_messages(self, entity: EntityId, msg_ids: list[int]):
        pass

    # @abstractmethod
    # def init_message(self, entity: EntityId) -> MockedMessage:
    #     pass
    @abstractmethod
    def get_storage_document(self, doc_id: DocId) -> StorageItemDocument:
        pass

    @abstractmethod
    def get_storage_photo(self, doc_id: DocId) -> StorageItemPhoto:
        pass

    @abstractmethod
    async def create_storage_document(
        self,
        file: str,
        file_name: str | bool = True,
    ) -> StorageItemDocument:
        pass

    async def create_storage_photo(
        self,
        file: str,
    ) -> StorageItemPhoto:

        ...
