import errno
import os
from dataclasses import dataclass, field

import pyfuse3

import tgmount.vfs as vfs
from tgmount.util.col import map_keys

from .inode import InodesRegistry, RegistryItem
from .operations import FileSystemOperations


class FileSystemOperationsWritable(FileSystemOperations):
    def __init__(self, root: vfs.DirLike):
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
            self.logger.error("create(): missing parent")
            raise pyfuse3.FUSEError(errno.EIO)

        if not vfs.DirLike.guard(parent_dir.data.structure_item):
            self.logger.error("create(): parent is not a folder")
            raise pyfuse3.FUSEError(errno.EIO)

        if not parent_dir.data.structure_item.writable:
            self.logger.warning("create(): parent_dir is not writable")
            raise pyfuse3.FUSEError(errno.EPERM)

        if not vfs.DirContentProtoWritable.guard(
            parent_dir.data.structure_item.content
        ):
            self.logger.warning("create(): parent_dir content is not writable")
            raise pyfuse3.FUSEError(errno.EPERM)

        filelike = await parent_dir.data.structure_item.content.create(
            self._bytes_to_str(name)
        )

        attrs = self._create_attributes_for_item(filelike, inode=None)
        fs_item = self.create_FileSystemItem(filelike, attrs)

        item = self.inodes.add_item_to_inodes(name, fs_item, parent_inode=parent_inode)

        fh = self._handles.open_fh(item, None)
        attrs.st_ino = item.inode

        if flags & os.O_RDWR or flags & os.O_WRONLY:
            pass

        return (pyfuse3.FileInfo(fh), attrs)

    """ 
    Write *buf* into *fh* at *off*.

    *fh* will be an integer filehandle returned by a prior `open` or
    `create` call.

    This method must return the number of bytes written. However, unless the
    file system has been mounted with the ``direct_io`` option, the file
    system *must* always write *all* the provided data (i.e., return
    ``len(buf)``).

    """

    async def write(self, fh: int, off: int, buf: bytes):
        self.logger.debug(f"= write(fh={fh},off={off},buf={len(buf)} bytes).")

        item, handle = self._handles.get_by_fh(fh)

        if item is None:
            self.logger.error(f"write(fh={fh}): missing item in open handles")
            return

        if not vfs.FileLike.guard(
            item.data.structure_item,
        ):
            self.logger.error(f"release({fh}): is not file")
            raise pyfuse3.FUSEError(errno.EIO)

        if not item.data.structure_item.writable:
            self.logger.error(f"write({fh}): is not writable")
            raise pyfuse3.FUSEError(errno.EPERM)
