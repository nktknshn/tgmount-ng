import asyncio
import copy
import os
from typing import AsyncGenerator, Coroutine, Mapping

import aiofiles
import aiofiles.os
import pytest

from tgmount import vfs


async def concurrentlys(*coros: Coroutine):
    ts = map(asyncio.create_task, coros)

    done, prending = await asyncio.wait(ts, return_when=asyncio.ALL_COMPLETED)

    if len(done) < len(coros):
        pytest.fail(f"some of the coros threw an exception: {done.pop().exception()}")

    return tuple(map(lambda r: r.result(), done))


async def concurrently(coro1: Coroutine, coro2: Coroutine):
    t1 = asyncio.create_task(coro1)
    t2 = asyncio.create_task(coro2)

    done, prending = await asyncio.wait([t1, t2], return_when=asyncio.ALL_COMPLETED)

    if len(done) < 2:
        pytest.fail(f"Some of the coros threw an exception: {done.pop().exception()}")

    [res1, res2] = done

    return res1.result(), res2.result()


class mdict:
    def __init__(self, root: Mapping) -> None:
        self._root: dict = copy.deepcopy(dict(root))
        self._current_dict = self._root
        self._path = []

    def enter(self, path: str):
        _path = vfs.napp(path, True)
        self._enter_path(_path)
        return self

    def _enter_path(self, path: list[str]):
        for p in path:
            self._enter(p)

        return self

    def _enter(self, key: str | None = None):
        if key is None:
            self._path = []
            self._current_dict = self._root
        else:
            self._path.append(key)
            self._current_dict = self._current_dict[key]
        return self

    def update(self, update: dict, *, at: str | None = None):
        if at is not None:
            self.enter(at)

        self._current_dict.update(copy.deepcopy(update))
        return self

    def go(self):
        pass

    def get(self):
        return self._root
