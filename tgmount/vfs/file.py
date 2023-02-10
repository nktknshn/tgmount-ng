from abc import abstractmethod
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import (
    Any,
    Awaitable,
    Callable,
    Optional,
)

import aiofiles
from tgmount.util.col import bytearray_write

from tgmount.vfs.types.file import (
    FileContent,
    FileContentProto,
    FileContentWritableProto,
    FileLike,
    FileContentStringProto,
    FileContentStringWritable,
)
from tgmount.util.lock import Lock

logger = logging.getLogger("tgvfs")


def vfile(
    fname: str,
    content: FileContentProto,
    creation_time: Optional[datetime] = None,
    extra: Optional[Any] = None,
    writable=False,
):
    if creation_time is None:
        creation_time = datetime.now()

    return FileLike(fname, content, creation_time, extra, writable)


def file_content(
    size: int,
    read_func: Callable[[Any, int, int], Awaitable[bytes]],
):
    return FileContent(size=size, read_func=read_func)


def simple_read(content: str):
    async def _inner(handle, off, size):
        return str.encode(content[off : off + size])

    return _inner


def text_content(text: str):
    return FileContent(
        size=len(str.encode(text)),
        read_func=simple_read(text),
    )


def text_file(fname: str, text_str: str, creation_time=None):
    return FileLike(
        fname,
        text_content(text_str),
        creation_time if creation_time is not None else datetime.now(),
    )


def file_content_from_bytes(bs: bytes) -> FileContent:
    bio = BytesIO()
    bio.write(bs)
    return file_content_from_io(bio)


def file_content_from_io(b: BytesIO) -> FileContent:
    lock = Lock(f"file_content_from_io()", logger=logger)

    async def _read(f: BytesIO, off, size):
        logger.debug(f"file_content_from_io.read(off={off}, size={size})")

        async with lock:
            f.seek(off)
            return f.read(size)

    async def _open():
        logger.debug(f"file_content_from_io.open()")
        async with lock:
            return b

    async def _seek(b: BytesIO, c, w=0):
        logger.debug(f"file_content_from_io.seek(c={c}, w={w})")
        async with lock:
            b.seek(c, w)

    async def _tell(b: BytesIO):
        logger.debug(f"file_content_from_io.tell()")
        async with lock:
            return b.tell()

    async def _close(b: BytesIO):
        logger.debug(f"file_content_from_io.close()")
        async with lock:
            b.close()

    return FileContent(
        size=b.getbuffer().nbytes,
        open_func=_open,
        read_func=_read,
        close_func=_close,
        seek_func=_seek,
        tell_func=_tell,
    )


def file_content_from_file(src_path: str) -> FileContentProto:
    lock = Lock(f"from_file({src_path})", logger=logger)

    async def _read(f, off, size):
        logger.debug(f"file_to_file_content.read, off={off}, size={size}")

        async with lock:
            await f.seek(off)
            return await f.read(size)

    async def _open():
        logger.debug(f"file_to_file_content.open")
        async with lock:
            return await aiofiles.open(src_path, "rb")

    async def _seek(f, c, w=0):
        logger.debug(f"file_to_file_content.seek, c={c}, w={w}")
        async with lock:
            await f.seek(c, w)

    async def _tell(f):
        async with lock:
            return await f.tell()

    async def _close(f):
        async with lock:
            await f.close()

    return FileContent(
        size=os.path.getsize(src_path),
        open_func=_open,
        read_func=_read,
        close_func=_close,
        seek_func=_seek,
        tell_func=_tell,
    )


async def read_file_content_bytes(fc: FileContentProto) -> bytes:
    handle = await fc.open_func()
    data = await fc.read_func(handle, 0, fc.size)
    await fc.close_func(handle)

    return data


class FileContentWritableConsumer(FileContentWritableProto):
    """Consumes all the bytes. The result will be available in `close_func`"""

    size: int = 0

    def __init__(self) -> None:
        self._data: bytearray = bytearray()

    async def seek_func(self, handle, n: int, w: int):
        raise NotImplementedError()

    async def read_func(self, handle, off: int, size: int) -> bytes:
        raise NotImplementedError()

    tell_func: Optional[Callable[[Any], Awaitable[int]]] = None

    async def write(self, handle: None, off: int, buf: bytes):
        bytearray_write(self._data, off, buf)
        self.size = len(self._data)
        return len(buf)

    @abstractmethod
    async def open_func(self) -> None:
        return

    @abstractmethod
    async def close_func(self, handle):
        return
