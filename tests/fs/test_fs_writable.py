import pyfuse3
import asyncio
import logging
from typing import Sequence
import aiofiles
import pytest
from tests.integrational.fixtures import FixtureFiles, files

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
async def test_fs_operations1(mnt_dir: str, caplog, files: FixtureFiles):
    ctx = Context(mnt_dir, caplog)
    # ctx.init_logging(logging.DEBUG, debug_fs_ops=True)

    dir1_files = [
        vfs.vfile("file1.txt", FileContentStringWritable("file content")),
    ]

    structure = vfs.root(
        vfs.dir_content_from_source(
            [
                vfs.DirLike(
                    "dir1",
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

        await asyncio.create_subprocess_shell(
            f"cp {files.zip_debrecen.path} {ctx.path('/')}",
        )

    await ctx.run_test(lambda: fs1, test)


@pytest.mark.asyncio
async def test_fs_operations2(mnt_dir: str, caplog, files: FixtureFiles):
    ctx = Context(mnt_dir, caplog)
    # ctx.init_logging(logging.DEBUG, debug_fs_ops=True)
    fs1 = FileSystemOperationsWritable(vfs.root(DirContentTest([])))

    async def test():
        await asyncio.create_subprocess_shell(
            f"cp '{files.file_10mb}' {ctx.path('/')}",
        )

        await asyncio.sleep(3.0)

        assert await ctx.listdir("/") == ["file_10mb"]

    await ctx.run_test(lambda: fs1, test)
