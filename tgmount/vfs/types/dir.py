from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Iterable,
    Optional,
    Protocol,
    Sequence,
    TypeGuard,
    TypeVar,
    Union,
)

from tgmount.vfs.types.file import FileLike, FileContentWritableProto

T = TypeVar("T")

DirContentItem = Union["DirLike", FileLike]


OpenDirFunc = Callable[[], Awaitable[Any]]
ReleaseDirFunc = Callable[[T], Awaitable[Any]]


class DirContentProto(Protocol[T]):
    """
    Main interface describing a content of a folder. Intended to be
    stateless, storing the state in the handle by type `T` returned by
    `opendir_func`
    """

    @abstractmethod
    async def readdir_func(self, handle: T, off: int) -> Iterable[DirContentItem]:
        pass

    @abstractmethod
    async def opendir_func(self) -> T:
        pass

    @abstractmethod
    async def releasedir_func(self, handle: T):
        pass

    @staticmethod
    def guard(item: Any) -> TypeGuard["DirContentProto[Any]"]:
        return hasattr(item, "readdir_func")


class DirContentWritableProto(DirContentProto[T], Protocol[T]):
    @abstractmethod
    async def create(self, filename: str) -> FileLike:
        pass

    @staticmethod
    def guard(dc: DirContentProto) -> TypeGuard["DirContentWritableProto"]:
        return hasattr(dc, "create")


@dataclass
class DirLike:
    """Represents a folder with a name and content"""

    name: str
    content: "DirContentProto"

    creation_time: datetime = datetime.now()

    extra: Optional[Any] = None

    writable: bool = False

    @staticmethod
    def guard(item: Any) -> TypeGuard["DirLike"]:
        return isinstance(item, DirLike)


class DirContent(DirContentProto[T]):
    """implements `DirContentProto` with functions"""

    def __init__(
        self,
        readdir_func,
        releasedir_func=None,
        opendir_func=None,
    ):
        self._readdir_func = readdir_func
        self._releasedir_func: Optional[ReleaseDirFunc[T]] = releasedir_func
        self._opendir_func: Optional[OpenDirFunc] = opendir_func

    async def readdir_func(self, handle: T, off: int) -> Iterable[DirContentItem]:
        return await self._readdir_func(handle, off)

    async def opendir_func(self):
        if self._opendir_func:
            return await self._opendir_func()

    async def releasedir_func(self, handle: T):
        if self._releasedir_func:
            return await self._releasedir_func(handle)


class DirContentList(DirContentProto[list[DirContentItem]]):
    """Immutable dir content sourced from a list of `DirContentItem`"""

    def __init__(self, content_list: Sequence[DirContentItem]):
        self.content_list = list(content_list)

    async def opendir_func(self) -> list[DirContentItem]:
        return self.content_list[:]

    async def releasedir_func(self, handle: list[DirContentItem]):
        return

    async def readdir_func(
        self, handle: list[DirContentItem], off: int
    ) -> Iterable[DirContentItem]:
        return handle[off:]


class DirContentListWritable(DirContentList, DirContentWritableProto):
    @abstractmethod
    async def create_filelike(self, filename: str) -> FileLike:
        pass

    async def create(self, filename: str) -> FileLike:
        fl = await self.create_filelike(filename)
        self.content_list.append(fl)
        return fl
