from abc import abstractmethod
from typing import Any, Awaitable, Callable, Mapping, Optional, Protocol, Type
from tgmount import config, vfs
from tgmount.common.extra import Extra
from tgmount.config.config import DirConfigReader, Extensions
from tgmount.config.reader import PropertyReader, TgmountConfigExtensionProto
from tgmount.fs.writable import FileSystemOperationsWritable
from tgmount.tgclient import uploader
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgmount.extensions.types import (
    TgmountExtensionProto,
    VfsTreeExtensionProto,
)
from tgmount.tgmount.file_factory.filefactory import is_telegram_extra
from tgmount.tgmount.tgmount_builderbase import (
    TgmountBuilderBase,
)
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.types import TgmountBuilderExtensionProto
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir, VfsTreeDirContent
from tgmount.tgmount.vfs_tree_producer import VfsTreeProducer
from tgmount.tgmount.vfs_tree_producer_types import (
    VfsTreeProducerExtensionProto,
    VfsDirConfig,
)
from telethon import events

from tgmount.util import map_none, no, yes
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.util.col import bytearray_write
from tgmount.vfs.file import FileContentWritableConsumer
from tgmount.vfs.types.dir import DirContentWritableProto
from tgmount.vfs.types.file import FileContentWritableProto

from .logger import logger


class VfsDirTreeExtraWritable:
    uploader: TelegramFileUploader | None


class WritableDirConfig(Protocol):
    upload: bool | None


class WritableResources(Protocol):
    uploaders: Mapping[str, TelegramFileUploader]


class VfsTreeWritable(VfsTree):
    def __init__(self) -> None:
        logger.debug("VfsTreeWritable()")
        super().__init__()

    async def get_dir_content(self, path: str = "/") -> VfsTreeDirContent:
        d = await self.get_dir(path)

        writable = map_none(
            d.extra, lambda e: e.get("writable", VfsDirTreeExtraWritable)
        )

        if yes(writable) and yes(writable.uploader):
            return VfsTreeDirContentWritable(self, path, writable.uploader)

        return VfsTreeDirContent(self, path)


class TgmountExtensionWritable(TgmountExtensionProto):
    prop = "writable"

    VfsTree = VfsTreeWritable
    FileSystemOperations = FileSystemOperationsWritable

    def __init__(self) -> None:
        self._uploaders: dict[str, TelegramFileUploader] = {}

    @staticmethod
    def config_extension() -> Extensions:
        return {
            DirConfigReader: [TgmountExtensionWritable()],
        }

    def extend_config(self, reader: PropertyReader, extra: Extra):
        extra.create(self.prop)
        extra.writable.upload = reader.boolean("upload", optional=True)

    async def extend_tgmount(
        self,
        cfg: config.Config,
        builder: TgmountBuilderBase,
        resources: TgmountResources,
        tgmount: TgmountBase,
    ):
        for uploader in self._uploaders.values():
            uploader.subscribe(
                lambda sender, msg: tgmount.on_new_message(
                    uploader._entity, events.NewMessage.Event(msg)
                )
            )

    async def extend_resources(
        self,
        cfg: config.Config,
        builder: TgmountBuilderBase,
        resources: TgmountResources,
    ):
        extra = resources.extra.create(self.prop)

        uploaders: dict[str, TelegramFileUploader] = {}

        for dir_config in TgmountConfigReader().walk_dir_props(cfg.root):
            if dir_config.extra.get(self.prop, WritableDirConfig).upload and yes(
                dir_config.source
            ):
                entity = cfg.message_sources.sources[dir_config.source.source].entity

                uploaders[dir_config.source.source] = TelegramFileUploader(
                    builder.client, entity
                )
                # uploaders[dir_config.source.source].subscribe()

        self._uploaders = extra.uploaders = uploaders

    async def extend_vfs_tree_dir(
        self,
        resources: TgmountResources,
        vfs_config: VfsDirConfig,
        tree_dir: VfsTreeDir,
    ):
        dir_config_extra = vfs_config.dir_config.extra.get(self.prop, WritableDirConfig)

        writable_resources = resources.extra.get(self.prop, WritableResources)

        if not yes(writable_resources):
            return

        if not yes(dir_config_extra):
            return

        if not dir_config_extra.upload:
            return
        if not yes(vfs_config.dir_config.source):
            return

        uploader = writable_resources.uploaders.get(vfs_config.dir_config.source.source)

        if not yes(uploader):
            return

        if not yes(tree_dir.extra):
            tree_dir.extra = Extra()

        extra = tree_dir.extra.create(self.prop, VfsDirTreeExtraWritable)

        extra.uploader = uploader


class VfsTreeDirContentWritable(VfsTreeDirContent, DirContentWritableProto):
    logger = logger.getChild("VfsTreeDirContentWritable")

    def __init__(
        self, tree: "VfsTree", path: str, uploader: TelegramFileUploader
    ) -> None:
        super().__init__(tree, path)
        self._uploader = uploader
        self._uploading_files: dict[str, vfs.FileLike] = {}
        self._logger = logger.getChild(path, suffix_as_tag=True)

    async def on_complete(self, filename: str, message: MessageDownloadable):
        thedir = await self._tree.get_dir(self._path)
        await thedir.remove_content(self._uploading_files[filename])
        del self._uploading_files[filename]

    async def remove(self, file_name: str):
        thedir = await self._tree.get_dir(self._path)
        item = await thedir.get_by_name(file_name)

        if yes(item):
            await thedir.remove_content(item)

            if is_telegram_extra(item.extra) and yes(item.extra[0]):
                await self._uploader.remove([item.extra[0]])
            else:
                self._logger.error(f"Missing file extra")
        else:
            self._logger.error(
                f"remove({file_name}). Item with the name was not found in the folder."
            )
        # return await super().remove(filename)

    async def create(self, filename: str) -> vfs.FileLike:
        logger.debug(f"VfsTreeDirContentWritable.create({filename})")

        vfs_dir = await self._tree.get_dir(self._path)

        filelike = vfs.FileLike(
            filename,
            content=FileContentWritableUpload(
                self._uploader, filename, self.on_complete
            ),
            writable=True,
        )

        # we don't need to notify the fs since it already knows about the file
        #
        await vfs_dir.put_content([filelike], notify=False)

        self._uploading_files[filename] = filelike
        return filelike


class FileContentWritableUpload(FileContentWritableConsumer):
    def __init__(
        self,
        uploader: TelegramFileUploader,
        filename: str,
        on_complete: Callable[[str, MessageDownloadable], Awaitable],
    ) -> None:
        super().__init__()
        self._uploader = uploader
        self._filename = filename
        self._on_complete = on_complete

    async def open_func(self) -> None:
        pass

    async def close_func(self, handle):
        msg = await self._uploader.upload(
            bytes(self._data),
            file_name=self._filename,
            file_size=self.size,
        )

        await self._on_complete(self._filename, msg)
