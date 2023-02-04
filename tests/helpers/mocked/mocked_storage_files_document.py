from copy import deepcopy

from telethon import types


from tgmount.util import none_fallback

from .mocked_message import (
    MockedDocument,
    MockedPhoto,
)

EntityId = str


class StorageItemDocument:
    def __init__(
        self,
        id: int,
        file_bytes: bytes,
        access_hash: int,
        file_reference: bytes,
        file_name: str | None = None,
        attributes: list[types.TypeDocumentAttribute] | None = None,
    ) -> None:
        self.id = id
        self._bytes: bytes = file_bytes
        self._file_name = file_name
        self._attributes = none_fallback(attributes, [])
        self._access_hash = access_hash
        self._file_reference = file_reference
        self._size = len(file_bytes)

    @property
    def file_reference(self):
        return self._file_reference

    @file_reference.setter
    def file_reference(self, file_reference: bytes):
        self._file_reference = file_reference

    @property
    def size(self):
        return self._size

    @property
    def attributes(self):
        return self._attributes

    @property
    def name(self):
        return self._file_name

    @property
    def file_bytes(self):
        return self._bytes

    def get_document(self) -> MockedDocument:

        attributes = none_fallback(self._attributes, [])

        if self._file_name is not None:
            attributes.append(types.DocumentAttributeFilename(self._file_name))

        return MockedDocument(
            id=self.id,
            size=self._size,
            access_hash=self._access_hash,
            file_reference=self._file_reference,
            attributes=attributes,
        )

    def clone(self):
        return deepcopy(self)
