from abc import abstractmethod
from typing import Generic, Protocol, TypeGuard, TypeVar
from tgmount import vfs

T = TypeVar("T")


class TelegramFilesSourceProto(Generic[T], Protocol):
    @abstractmethod
    def file_content(self, message: T) -> vfs.FileContent:
        pass

    @abstractmethod
    async def read(self, message: T, offset: int, limit: int) -> bytes:
        ...
