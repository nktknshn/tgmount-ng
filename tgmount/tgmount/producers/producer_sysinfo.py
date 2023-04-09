import os
from typing import Any, Callable, Mapping, Protocol

from tgmount import fs, vfs
from tgmount.common.extra import Extra, Namespace
from tgmount.fs.operations import FileSystemOperations
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgmount.cached_filefactory_factory import CacheFileFactoryFactory
from tgmount.tgmount.tgmount_resources import TgmountResources
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.vfs.vfs_tree import VfsTreeDir
from tgmount.tgmount.vfs_tree_producer_types import (
    VfsTreeDirProducerConfig,
    VfsTreeDirProducerProto,
)
from tgmount.util import nn
from tgmount.util.col import map_keys
from tgmount.util.path import norm_path, paths_to_tree, split_path, walk_paths_tree

from .logger import module_logger


def encode(s: str):
    return s.encode("utf-8")


class SysInfoFile(vfs.FileContentStringProto):
    size = 666666


class SysInfoCaches(SysInfoFile):
    """fuse doesn't support reading files with zero bytes size like in procfs"""

    size = 666666

    def __init__(self, caches: CacheFileFactoryFactory) -> None:
        self._caches = caches

    async def get_string(self, handle: Any) -> str:
        result = ""

        for cache_id in self._caches.ids:
            cache = self._caches.get_cache_by_id(cache_id)

            if not nn(cache):
                continue

            total_stored = await cache.total_stored()
            documents = cache.documents

            result += f"{cache_id}\n"
            result += f"Capacity\t{cache.capacity}\n"
            result += f"Block size\t{cache.block_size}\n"

            result += f"Total cached\t{total_stored} bytes\n"
            result += f"\n"

            result += f"chat_id\t\tmessage_id\tdocument_id\tfilename\tcached\n"

            for message, stored_bytes in await cache.stored_per_message():
                result += f"{message.chat_id}\t{message.id}\t{MessageDownloadable.document_or_photo_id(message)}\t{message.file.name}\t{stored_bytes} bytes\n"

            result += f"\n"

        return result


class SysInfoFileSystem(SysInfoFile):
    def __init__(
        self,
        get_fs: Callable[[], fs.FileSystemOperations],
    ) -> None:
        self._get_fs = get_fs

    async def get_string(self, handle: Any) -> str:
        result = ""
        inodes = self._get_fs().inodes.get_inodes()

        result += f"Inodes count: {len(inodes)}"

        return result


class SysInfoExtra(Protocol):
    items: dict[str, SysInfoFile]


class CacheFileFactoryFactoryProvider(Protocol):
    caches: CacheFileFactoryFactory


class VfsTreeProducerSysInfo(VfsTreeDirProducerProto):
    logger = module_logger.getChild("VfsTreeProducerSysInfo")

    def __init__(
        self,
        resources: TgmountResources,
        vfs_tree_dir: VfsTreeDir,
    ) -> None:
        self._vfs_tree_dir = vfs_tree_dir
        self._resources = resources
        self._items = resources.extra.get("sysinfo", SysInfoExtra).items

    @classmethod
    async def from_config(
        cls,
        resources: TgmountResources,
        config: VfsTreeDirProducerConfig,
        arg: Mapping,
        vfs_tree_dir: VfsTreeDir,
    ) -> "VfsTreeProducerProto":
        return VfsTreeProducerSysInfo(resources=resources, vfs_tree_dir=vfs_tree_dir)

    @staticmethod
    def create_sysinfo_extra(
        extra: Extra, resources: TgmountResources, fs: FileSystemOperations
    ):
        sysinfo_extra = extra.create("sysinfo", SysInfoExtra)
        sysinfo_extra.items = {}
        VfsTreeProducerSysInfo.add_sysinfo_item(
            extra, "/cache", SysInfoCaches(resources.caches)
        )
        VfsTreeProducerSysInfo.add_sysinfo_item(
            extra, "/fs/inodes", SysInfoFileSystem(fs)
        )

    @staticmethod
    def add_sysinfo_item(extra: Extra, path: str, item: SysInfoFile):
        sysinfo_extra = extra.try_get("sysinfo", SysInfoExtra)

        if sysinfo_extra is None:
            VfsTreeProducerSysInfo.logger.warning(
                f"Error adding {path}. Missing sysinfo extra."
            )
            return

        sysinfo_extra.items[path] = item

    async def produce(self):
        items_tree = paths_to_tree(self._items.keys())
        items_norm = map_keys(norm_path, self._items)

        for path in walk_paths_tree(items_tree):
            if path not in items_norm:
                # print(f"Create dir {path}. items_norm={items_norm}")
                await self._vfs_tree_dir.create_dir(path)

        for path, item_content in items_norm.items():
            dirpath, filename = split_path(path)

            await self._vfs_tree_dir.put_content(
                vfs.FileLike(filename, item_content), dirpath
            )
