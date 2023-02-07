import pyfuse3
import asyncio
import logging
from typing import Sequence
import aiofiles
import pytest

from tgmount import vfs
from tgmount.fs import FileSystemOperations, FileSystemOperationsWritable
from tgmount.vfs.dir import dir_content
from tgmount.vfs.types.file import FileContentStringWritable, FileLike

from ..helpers.fixtures_common import mnt_dir
from .helpers import Context


class DirContentTest(vfs.DirContentListWritable):
    def __init__(self, content_list: Sequence[vfs.DirContentItem]):
        super().__init__(content_list)

    async def create_filelike(self, filename: str) -> FileLike:
        return vfs.FileLike(
            filename,
            vfs.FileContentStringWritable(),
            writable=True,
        )


@pytest.mark.asyncio
async def test_FileContentStringWritable(mnt_dir: str, caplog):
    content = FileContentStringWritable()

    await content.write(None, 0, b"12345")

    assert await content.read_func(None, 0, 5) == b"12345"

    assert await content.write(None, 3, b"12345") == 5

    assert await content.read_func(None, 0, 8) == b"12312345"
    assert content.size == 8


@pytest.mark.asyncio
async def test_fs_operations1(mnt_dir: str, caplog):
    ctx = Context(mnt_dir, caplog)
    ctx.init_logging(logging.DEBUG, debug_fs_ops=True)

    dir1_files = [
        vfs.vfile(
            "file1.txt", FileContentStringWritable("file content"), writable=True
        ),
    ]

    structure = vfs.root(
        vfs.dir_content_from_source(
            [
                vfs.DirLike(
                    "dir1",
                    writable=True,
                    content=DirContentTest(dir1_files),
                )
            ]
        ),
    )

    fs1 = FileSystemOperationsWritable(structure)

    async def test():
        assert await ctx.listdir_set("/") == {"dir1"}
        assert await ctx.listdir_set("/dir1") == {"file1.txt"}

        assert await ctx.read_text("/dir1/file1.txt") == "file content"

        # async with await ctx.open("/dir1/file1.txt", "w") as f:
        #     await f.write("HELLO")

        # assert await ctx.read_text("/dir1/file1.txt") == "HELLOcontent"

        async with await ctx.open("/dir1/file2.txt", "w") as f:
            await f.write("HELLO")

        assert await ctx.listdir_set("/dir1") == {"file1.txt", "file2.txt"}

        assert (await ctx.stat("/dir1/file2.txt")).st_size == 5

        assert await ctx.read_text("/dir1/file2.txt") == "HELLO"

    await ctx.run_test(lambda: fs1, test)
