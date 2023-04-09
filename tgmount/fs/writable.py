import errno
import os
from dataclasses import dataclass, field

import pyfuse3

import tgmount.vfs as vfs
from tgmount.util.col import map_keys
from tgmount.vfs.types.file import FileContentWritableProto

from .inode import InodesRegistry, RegistryItem
from .logger import logger
from .readable import FileSystemOperationsBase
from .update import FileSystemOperationsUpdatable
from .util import exception_handler, flags_to_str


class FileSystemOperationsWritable(FileSystemOperationsBase):
    logger = logger.getChild("FileSystemOperationsWritable")

    """ XXX update lock? """

    def __init__(self, root: vfs.DirContentProto | None):
        super().__init__(root)

    """ 
    Create a file with permissions *mode* and open it with *flags*.

    *ctx* will be a `RequestContext` instance.

    The method must return a tuple of the form *(fi, attr)*, where *fi* is a
    FileInfo instance handle like the one returned by `open` and *attr* is
    an `EntryAttributes` instance with the attributes of the newly created
    directory entry.

    (Successful) execution of this handler increases the lookup count for
    the returned inode by one.
    """

    @exception_handler
    async def create(
        self,
        parent_inode: int,
        name: bytes,
        mode: int,
        flags: int,
        ctx: pyfuse3.RequestContext,
    ):
        parent_dir = self.inodes.get_item_by_inode(parent_inode)

        if parent_dir is None:
            self.logger.error(f"create({parent_inode}): missing parent")
            raise pyfuse3.FUSEError(errno.EIO)

        self.logger.debug(
            f"create(f{parent_dir.name}, {name}, {mode}, flags={flags_to_str(flags)})"
        )

        if not flags & os.O_WRONLY:
            self.logger.warning("create(): write-only creation is only supported.")
            raise pyfuse3.FUSEError(errno.EPERM)

        if not vfs.DirLike.guard(parent_dir.data.structure_item):
            self.logger.error("create(): parent is not a folder")
            raise pyfuse3.FUSEError(errno.EIO)

        if not vfs.DirContentCanCreateProto.guard(
            parent_dir.data.structure_item.content
        ):
            self.logger.warning("create(): parent_dir content is not writable.")
            raise pyfuse3.FUSEError(errno.EPERM)

        filelike = await parent_dir.data.structure_item.content.create(
            self._bytes_to_str(name)
        )

        item = self.add_subitem(filelike, parent_inode)

        fh = self._handles.open_fh(item, None)

        return (pyfuse3.FileInfo(fh), item.data.attrs)

    """ 
    Write *buf* into *fh* at *off*.

    *fh* will be an integer file handle returned by a prior `open` or
    `create` call.

    This method must return the number of bytes written. However, unless the
    file system has been mounted with the ``direct_io`` option, the file
    system *must* always write *all* the provided data (i.e., return
    ``len(buf)``).

    """

    @exception_handler
    async def write(self, fh: int, off: int, buf: bytes):
        self.logger.debug(f"= write(fh={fh},off={off},buf={len(buf)} bytes).")

        item, handle = self._handles.get_by_fh(fh)

        if item is None:
            self.logger.error(f"write(fh={fh}): missing item in open handles.")
            return

        self.logger.debug(f"writing into {item.name}. inode = {item.inode}")

        if not vfs.FileLike.guard(
            item.data.structure_item,
        ):
            self.logger.error(f"write({item.name}): is not a file")
            raise pyfuse3.FUSEError(errno.EIO)

        content = item.data.structure_item.content

        if not FileContentWritableProto.guard(content):
            self.logger.error(f"write({item.name}): content is not writable.")
            raise pyfuse3.FUSEError(errno.EPERM)

        byte_written = await content.write(handle, off, buf)

        item.data.attrs.st_size = content.size

        return byte_written

    @exception_handler
    async def release(self, fh):
        item, data = self._handles.get_by_fh(fh)

        return await super().release(fh)

    """ 
    Remove a (possibly special) file.

    This method must remove the (special or regular) file *name* from the
    direcory with inode *parent_inode*.  *ctx* will be a `RequestContext`
    instance.

    If the inode associated with *file* (i.e., not the *parent_inode*) has a
    non-zero lookup count, or if there are still other directory entries
    referring to this inode (due to hardlinks), the file system must remove
    only the directory entry (so that future calls to `readdir` for
    *parent_inode* will no longer include *name*, but e.g. calls to
    `getattr` for *file*'s inode still succeed). (Potential) removal of the
    associated inode with the file contents and metadata must be deferred to
    the `forget` method to be carried out when the lookup count reaches zero
    (and of course only if at that point there are no more directory entries
    associated with the inode either).

    """

    @exception_handler
    async def unlink(self, parent_inode: int, name: bytes, ctx):
        parent_item = self._inodes.get_item_by_inode(parent_inode)

        if parent_item is None:
            self.logger.error(
                f"unlink({parent_inode}): missing parent_inode={parent_inode}"
            )
            raise pyfuse3.FUSEError(errno.ENOENT)

        self.logger.debug(f"= unlink({parent_item.name}, {name})")

        if not vfs.DirLike.guard(parent_item.data.structure_item):
            self.logger.error("unlink(): parent_item is not DirLike")
            raise pyfuse3.FUSEError(errno.ENOENT)

        if not self._inodes.was_content_read(parent_item.inode):
            await self._read_dir_content(parent_item)
            self._inodes.set_content_read(parent_item.inode)

        if not vfs.DirContentCanRemoveProto.guard(
            parent_item.data.structure_item.content
        ):
            self.logger.warning("create(): parent_item content can't remove.")
            raise pyfuse3.FUSEError(errno.EPERM)

        await parent_item.data.structure_item.content.remove(
            self._bytes_to_str(name),
        )

        # item = self._inodes.get_child_item_by_name(name, parent_inode)
        # self.remove_subitem(parent_inode, name)
