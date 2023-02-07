import asyncio
import logging
import os
import threading
from typing import TypedDict

import pytest

from tgmount import fs, vfs
from tgmount.tglog import init_logging
from tgmount.util import none_fallback

from ..helpers.fixtures_common import mnt_dir

# from ..helpers.spawn import GetProps, OnEventCallbackSet, spawn_fs_ops
# Main1Props = TypedDict("Main1Props", debug=int, ev0=threading.Event)

from .helpers import Context

dirc = vfs.dir_content_from_source
root = vfs.root


def f(name: str, content=None):
    return vfs.vfile(
        name, content=none_fallback(content, vfs.text_content("we dont care"))
    )


def d(name: str, content):
    return vfs.vdir(name, content=content)


def async_lambda(f):
    async def _inner():
        f()

    return _inner


@pytest.mark.asyncio
async def test_fs_rename_filelikes(mnt_dir, caplog):
    ctx = Context(mnt_dir, caplog)
    # ctx.debug = logging.DEBUG

    root1 = vfs.root(
        vfs.dir_content_from_source(
            {
                "subf": {
                    "aaa": vfs.text_content("aaaaaaa"),
                    "bbb": vfs.text_content("bbbbbbb"),
                }
            }
        )
    )

    fs1 = fs.FileSystemOperationsUpdatable(root1)

    async def test():
        assert await ctx.listdir_set("subf") == {"aaa", "bbb"}

        assert await ctx.read_text("subf/aaa") == "aaaaaaa"

        assert (await ctx.stat("subf/aaa")).st_size == 7

        await fs1.update(
            fs.FileSystemOperationsUpdate(
                update_items={
                    "/subf/aaa": vfs.FileLike("aaa", vfs.text_content("!!!")),
                    "/subf/bbb": vfs.FileLike("ccc", vfs.text_content("###")),
                }
            )
        )

        # await asyncio.sleep(1)

        assert await ctx.listdir_set("subf") == {"aaa", "ccc"}

        assert (await ctx.stat("subf/aaa")).st_size == 3

        assert await ctx.read_text("subf/aaa") == "!!!"

        with pytest.raises(FileNotFoundError):
            s = await ctx.stat("subf/bbb")
            print(s)

        assert (await ctx.stat("subf/ccc")).st_size == 3

        assert await ctx.read_text("subf/ccc") == "###"

        assert (await ctx.stat("subf/aaa")).st_ctime_ns < (
            await ctx.stat("subf/aaa")
        ).st_mtime_ns

    await ctx.run_test(lambda: fs1, test)


@pytest.mark.asyncio
async def test_fs1(mnt_dir, caplog):
    ctx = Context(mnt_dir)

    root1 = vfs.root(
        vfs.dir_content_from_source(
            {
                "subf": {
                    "aaa": vfs.text_content("aaaaaaa"),
                    "bbb": vfs.text_content("bbbbbbb"),
                }
            }
        )
    )

    fs1 = fs.FileSystemOperationsUpdatable(root1)

    async def test():
        assert await ctx.listdir_set("subf") == {"aaa", "bbb"}

        await fs1.update(
            fs.FileSystemOperationsUpdate(
                removed_files=[
                    "/subf/aaa",
                    "/subf/bbb",
                ],
                new_files={
                    "/subf/ccc": vfs.text_file("ccc", "ccc content"),
                },
            )
        )

        assert await ctx.listdir_set("subf") == {"ccc"}

    await ctx.run_test(lambda: fs1, test)
