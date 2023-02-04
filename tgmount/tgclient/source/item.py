from abc import abstractmethod
from typing import Optional, Protocol

from ..types import DocId, InputDocumentFileLocation, InputPhotoFileLocation

InputLocation = InputDocumentFileLocation | InputPhotoFileLocation


class FileSourceItem(Protocol):
    id: DocId
    file_reference: bytes
    access_hash: int
    size: int

    @abstractmethod
    def input_location(self, file_reference: Optional[bytes]) -> InputLocation:
        raise NotImplementedError()
