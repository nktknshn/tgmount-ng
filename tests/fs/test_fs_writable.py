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
async def test_fs_operations1(mnt_dir: str):
    ctx = Context(mnt_dir)

    dir1_files = [
        vfs.vfile("file1.txt", FileContentStringWritable("file content")),
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

    async def test():
        assert await ctx.listdir_set("/") == {"dir1"}

    await ctx.run_test(lambda: FileSystemOperationsWritable(structure), test)
