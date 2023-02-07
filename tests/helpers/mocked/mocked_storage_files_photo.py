from copy import deepcopy
from dataclasses import dataclass

from tgmount.tgclient.message_types import PhotoSizeProto, PhotoSizeProtoBasic
from tgmount.util import none_fallback

from .mocked_message import MockedPhoto


@dataclass
class MockedPhotoSize(PhotoSizeProtoBasic):
    type: str = "idk"
    w: int = 640
    h: int = 480
    size: int = 6666


class StorageItemPhoto:
    def __init__(
        self,
        id: int,
        file_bytes: bytes,
        access_hash: int,
        file_reference: bytes,
        sizes: list[PhotoSizeProto] | None = None,
    ) -> None:
        self.id = id
        self._bytes: bytes = file_bytes
        self._sizes = sizes
        self._file_reference = file_reference
        self._access_hash = access_hash
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
    def file_bytes(self):
        return self._bytes

    def get_photo(self) -> MockedPhoto:

        sizes = none_fallback(self._sizes, [MockedPhotoSize(size=self._size)])

        return MockedPhoto(
            id=self.id,
            sizes=sizes,
            access_hash=self._access_hash,
            file_reference=self._file_reference,
        )

    def clone(self):
        return deepcopy(self)
