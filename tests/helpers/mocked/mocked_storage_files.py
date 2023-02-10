from typing import Type
from telethon import types
from tgmount.tgclient.message_types import PhotoSizeProto
from tgmount.tgclient.types import DocId

from tgmount.util import random_int, nn

from .mocked_storage_files_document import StorageItemDocument
from .mocked_storage_files_photo import StorageItemPhoto


def random_file_reference() -> bytes:
    return bytes([random_int(255)() for _ in range(0, 32)])


StorageItem = StorageItemDocument | StorageItemPhoto


class StorageFiles:
    def __init__(self) -> None:
        self._files: dict[int, StorageItem] = {}
        self._last_id = 0

    def _next_id(self):
        self._last_id += 1
        return self._last_id

    def _new_access_hash(self):
        return random_int(100000)()

    def _new_file_reference(self) -> bytes:
        return random_file_reference()

    def put_file(self, file: StorageItemDocument):
        self._files[file.id] = file
        return file

    def add_document(
        self,
        file_bytes: bytes,
        file_name: str | None = None,
        attributes: list[types.TypeDocumentAttribute] | None = None,
    ):
        item = StorageItemDocument(
            id=self._next_id(),
            file_bytes=file_bytes,
            file_name=file_name,
            file_reference=self._new_file_reference(),
            access_hash=self._new_access_hash(),
            attributes=attributes,
        )

        self._files[item.id] = item

        return item

    def add_photo(
        self,
        file_bytes: bytes,
        sizes: list[PhotoSizeProto] | None = None,
    ):
        item = StorageItemPhoto(
            id=self._next_id(),
            file_bytes=file_bytes,
            file_reference=self._new_file_reference(),
            access_hash=self._new_access_hash(),
            sizes=sizes,
        )

        self._files[item.id] = item

        return item

    def get_document(self, doc_id: DocId) -> StorageItemDocument:
        item = self.get_item(doc_id, StorageItemDocument)

        if not isinstance(item, StorageItemDocument):
            raise RuntimeError(f"item is not document")

        return item

    def get_photo(self, doc_id: DocId) -> StorageItemPhoto:
        item = self.get_item(doc_id, StorageItemPhoto)

        if not isinstance(item, StorageItemPhoto):
            raise RuntimeError(f"item is not photo")
        return item

    def get_item(
        self,
        id: DocId,
        klass: Type[StorageItemDocument] | Type[StorageItemPhoto] | None = None,
    ) -> StorageItemDocument | StorageItemPhoto | None:
        item = self._files.get(id)

        if nn(klass) and not isinstance(item, klass):
            raise RuntimeError(f"Item is not {klass}")

        return item
