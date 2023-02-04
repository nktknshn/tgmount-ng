from typing import Optional

from telethon.tl.custom.file import File

from tgmount.tgclient.message_types import PhotoProto
from ..types import InputPhotoFileLocation, TypeInputFileLocation, DocId
from .item import FileSourceItem, InputLocation


def get_photo_input_location(
    photo: PhotoProto,
    type: str,
    file_reference: Optional[bytes] = None,
):
    return InputPhotoFileLocation(
        id=photo.id,
        access_hash=photo.access_hash,
        file_reference=file_reference
        if file_reference is not None
        else photo.file_reference,
        thumb_size=type,
    )


class SourceItemPhoto(FileSourceItem):
    id: DocId
    file_reference: bytes
    access_hash: int
    size: int

    def __init__(self, photo: PhotoProto) -> None:
        self.id = photo.id
        self.file_reference = photo.file_reference
        self.access_hash = photo.access_hash
        self.photo = photo
        self.size = self.get_size()
        # self.size = File(photo).size  # type: ignore

    def get_size(self):
        for s in self.photo.sizes:
            if s.type == self._type():
                if hasattr(s, "size"):
                    return s.size
                elif hasattr(s, "sizes"):
                    return max(s.sizes)

        raise RuntimeError(
            f"Error getting size for the photo: missing type {self._type()}"
        )

    def _type(self):

        max_size = self.photo.sizes[0]

        for s in self.photo.sizes:
            if getattr(max_size, "h", 0) < getattr(s, "h", 0):
                max_size = s

        return max_size.type

    def input_location(self, file_reference: Optional[bytes]) -> InputLocation:
        return get_photo_input_location(
            self.photo,
            self._type(),
            file_reference,
        )
