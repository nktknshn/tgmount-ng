import logging
from os import stat_result
import aiofiles
from typing import Any, AsyncGenerator, Iterable
from tgmount import tglog, vfs
from aiofiles import os

async_listdir = aiofiles.os.listdir  # type:ignore


async def async_walkdir(
    path: str,
) -> AsyncGenerator[tuple[str, list[str], list[str]], None]:
    # item: os.DirEntry
    subdirs: list[str] = []
    subfiles: list[str] = []

    for subitem in await aiofiles.os.listdir(path):  # type:ignore
        subitem_path = vfs.path_join(path, subitem)

        if await os.path.isdir(subitem_path):
            subdirs.append(subitem_path)
        elif await os.path.isfile(subitem_path):
            subfiles.append(subitem_path)

    yield path, subdirs, subfiles

    for subdir in subdirs:
        dir_iter = async_walkdir(subdir)
        async for res in dir_iter:
            yield res


OpenBinaryMode = Any


class MountContext:
    mnt_dir: str
    caplog: Any

    def _path(self, *path: str) -> str:
        return vfs.path_join(self.mnt_dir, *path)

    def init_logging(self, level: int, **kwargs):
        self.debug = level
        tglog.init_logging(level, **kwargs)

    async def listdir(self, *path: str, full_path=False) -> list[str]:
        return [
            vfs.path_join(*path, f) if full_path else f
            for f in await async_listdir(self._path(*path))
        ]

    async def listdir_len(self, *path: str) -> int:
        return len(await self.listdir(*path))

    async def listdir_set(self, *path: str, full_path=False) -> set[str]:
        return set(await self.listdir(*path, full_path=full_path))

    def walkdir(
        self, *path: str
    ) -> AsyncGenerator[tuple[str, list[str], list[str]], None]:
        return async_walkdir(self._path(*path))

    async def listdir_recursive(self, path: str) -> set[str]:
        res = []

        for dirpath, dirnames, filenames in await async_walkdir(path):  # type: ignore
            res.append(dirpath)
            res.extend([vfs.path_join(str(dirpath), str(fn)) for fn in filenames])

        return set(res)

    async def stat(self, path: str) -> stat_result:
        return await os.stat(self._path(path))

    async def open(self, path: str, *args):
        return aiofiles.open(self._path(path), *args)

    async def read_text(self, path: str) -> str:
        async with aiofiles.open(self._path(path), "r") as f:
            return await f.read()

    async def read_bytes(self, path: str) -> bytes:
        async with aiofiles.open(self._path(path), "rb") as f:
            return await f.read()

    async def read_texts(self, paths: Iterable[str]) -> list[str] | set[str]:
        res = []
        for p in paths:
            res.append(await self.read_text(p))
        if isinstance(paths, set):
            return set(res)
        return res

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, value):
        logging_level = (
            logging.DEBUG
            if value is True
            else logging.ERROR
            if value is False
            else value
        )
        self._debug = logging_level

        tglog.init_logging(logging_level)

        if self.caplog is not None:
            self.caplog.set_level(self._debug)
