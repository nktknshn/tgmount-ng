from typing import Any, Awaitable, Callable, Mapping, Optional, Protocol, Type

from telethon import events

from tgmount import config, vfs, fs
from tgmount.common.extra import Extra
from tgmount.config import DirConfigReader, ConfigExtensions, PropertyReader
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tglog import TgmountLogger
from tgmount.tgmount.extensions.types import TgmountExtensionProto
from tgmount.tgmount.file_factory.filefactory import is_telegram_extra
from tgmount.tgmount.producers.producer_sysinfo import (
    SysInfoExtra,
    SysInfoFile,
    VfsTreeProducerSysInfo,
)
from tgmount.tgmount.root_config_walker import TgmountRootConfigWalker
from tgmount.tgmount.tgmount_builderbase import TgmountBuilderBase
from tgmount.tgmount.tgmount_resources import TgmountResources
from tgmount.tgmount.tgmountbase import TgmountBase
from tgmount.tgmount.vfs_tree_producer_types import VfsDirConfig
from tgmount.util import map_none, nn
from tgmount.vfs import (
    FileContentWritableConsumer,
    DirContentCanCreateProto,
    VfsTree,
    VfsTreeDir,
    VfsTreeDirContent,
)
from tgmount.vfs.types.dir import DirContentCanRemoveProto

from .logger import logger


class VfsDirTreeExtraWritableExtra:
    uploader: TelegramFileUploader | None


class WritableDirConfigExtra(Protocol):
    upload: bool | None


class WritableResourcesExtra(Protocol):
    uploaders: Mapping[str, TelegramFileUploader]


class VfsTreeWritable(VfsTree):
    def __init__(self) -> None:
        logger.debug("VfsTreeWritable()")
        super().__init__()

    async def get_dir_content(self, path: str = "/") -> VfsTreeDirContent:
        """if the folder has extra with uploader"""
        d = await self.get_dir(path)

        writable = map_none(
            d.extra,
            lambda e: e.get(
                TgmountExtensionWritable.extension_id, VfsDirTreeExtraWritableExtra
            ),
        )

        if nn(writable) and nn(writable.uploader):
            return VfsTreeDirContentWritable(self, path, writable.uploader)

        return self.VfsTreeDirContent(self, path)


class VfsTreeDirContentCanRemove(VfsTreeDirContent, DirContentCanRemoveProto):
    # logger = logger.getChild("VfsTreeDirContentCanRemove")
    _logger: TgmountLogger
    _uploader: TelegramFileUploader
    # def __init__(
    #     self, tree: "VfsTree", path: str, uploader: TelegramFileUploader
    # ) -> None:
    #     super().__init__(tree, path)
    #     self._logger = logger.getChild(path, suffix_as_tag=True)

    #     self._uploader = uploader

    async def remove(self, file_name: str):
        thedir = await self._tree.get_dir(self._path)
        item = await thedir.get_by_name(file_name)

        if nn(item):
            await thedir.remove_content(item)

            if is_telegram_extra(item.extra) and nn(item.extra[0]):
                # XXX how to catch
                await self._uploader.remove([item.extra[0]])
            else:
                self._logger.error(
                    f"Missing message information in the file extra in {file_name}."
                )
        else:
            self._logger.error(
                f"remove({file_name}). Item with the name was not found in the folder."
            )


class VfsTreeDirContentCanUpload(VfsTreeDirContent, DirContentCanCreateProto):
    logger = logger.getChild("VfsTreeDirContentCanUpload")

    def __init__(
        self, tree: "VfsTree", path: str, uploader: TelegramFileUploader
    ) -> None:
        super().__init__(tree, path)
        self._logger = logger.getChild(path, suffix_as_tag=True)

        self._uploader = uploader
        self._uploading_files: dict[str, vfs.FileLike] = {}
        self._uploading_progress: dict[str, int] = {}

    async def create(self, filename: str) -> vfs.FileLike:
        logger.debug(f"VfsTreeDirContentWritable.create({filename})")

        vfs_dir = await self._tree.get_dir(self._path)

        filelike = vfs.FileLike(
            filename,
            content=FileContentWritableUpload(
                self._uploader, filename, self.on_complete, self.on_error
            ),
            writable=True,
        )

        # we don't need to notify the fs since it already knows about the file
        await vfs_dir.put_content([filelike], notify=False)

        self._uploading_files[filename] = filelike

        return filelike

    async def on_complete(self, filename: str, message: MessageDownloadable):
        await self._forget_file(filename)

    async def on_error(self, filename: str, error: Exception):
        await self._forget_file(filename)

    async def _forget_file(self, filename: str):
        thedir = await self._tree.get_dir(self._path)
        await thedir.remove_content(self._uploading_files[filename])
        del self._uploading_files[filename]


class VfsTreeDirContentWritable(
    VfsTreeDirContentCanRemove,
    VfsTreeDirContentCanUpload,
):
    def __init__(
        self, tree: "VfsTree", path: str, uploader: TelegramFileUploader
    ) -> None:
        super().__init__(tree, path, uploader)


class FileContentWritableUpload(FileContentWritableConsumer):
    """Reads all the bytes and uploads file to telegram on file close"""

    logger = logger.getChild("FileContentWritableUpload")

    def __init__(
        self,
        uploader: TelegramFileUploader,
        filename: str,
        on_complete: Callable[[str, MessageDownloadable], Awaitable],
        on_error: Callable[[str, Exception], Awaitable],
    ) -> None:
        super().__init__()
        self._uploader = uploader
        self._filename = filename
        self._on_complete = on_complete
        self._on_error = on_error

        self._logger = logger.getChild(self._filename, suffix_as_tag=True)

    async def open_func(self) -> None:
        pass

    async def close_func(self, handle):
        try:
            msg = await self._uploader.upload(
                bytes(self._data),
                file_name=self._filename,
                file_size=self.size,
            )

            await self._on_complete(self._filename, msg)
        except Exception as e:
            self._logger.error(f"Error uploading file {self._filename}")
            await self._on_error(self._filename, e)


class SysInfoUploaders(SysInfoFile):
    def __init__(self, uploaders: dict[str, TelegramFileUploader]) -> None:
        self._uploaders = uploaders

    async def get_string(self, handle) -> str:
        result = ""

        for entity_id, uploader in self._uploaders.items():
            result += f"entity_id: {entity_id}\n"

            for file_name, (uploaded, total, error_or_msg) in uploader.progress.items():
                result += f"{file_name}\t\t\t{uploaded}/{total}\t"

                if isinstance(error_or_msg, Exception):
                    result += f" error: {str(error_or_msg)}"
                elif MessageDownloadable.guard(error_or_msg):
                    result += f" complete. Message id: {error_or_msg.id}"
                else:
                    result += f" in progress..."

                result += "\n"
            result += "\n"
        return result


class TgmountExtensionWritable(TgmountExtensionProto):
    extension_id = "writable"

    VfsTree = VfsTreeWritable
    FileSystemOperations = fs.FileSystemOperations

    logger = logger.getChild("TgmountExtensionWritable")

    def __init__(self) -> None:
        self._uploaders: dict[str, TelegramFileUploader] = {}

    @staticmethod
    def config_extension() -> ConfigExtensions:
        return {
            DirConfigReader: [TgmountExtensionWritable()],
        }

    def extend_config(self, reader: PropertyReader, extra: Extra):
        extra.create(self.extension_id)
        extra.writable.upload = reader.boolean("upload", optional=True)

    async def extend_tgmount(self, builder: TgmountBuilderBase, tgmount: TgmountBase):
        for uploader in self._uploaders.values():
            # Because changes that are made through the client will not trigger
            # events we have to do it manually
            uploader.on_uploaded.subscribe(
                lambda sender, msg: tgmount.on_new_message(
                    uploader._entity, events.NewMessage.Event(msg)
                )
            )

    async def extend_vfs_tree(self, vfs_tree: VfsTree):
        pass

    def add_sysinfo_items(self, builder: TgmountBuilderBase):
        sysinfo_extra = builder.resources.extra.try_get("sysinfo", SysInfoExtra)

        if sysinfo_extra is None:
            return

        VfsTreeProducerSysInfo.add_sysinfo_item(
            builder.resources.extra,
            "/uploaders",
            SysInfoUploaders(self._uploaders),
        )

    async def extend_resources(self, builder: TgmountBuilderBase):
        writable_extra = builder.resources.extra.create(self.extension_id)

        uploaders: dict[str, TelegramFileUploader] = {}

        for dir_config in TgmountRootConfigWalker().walk_dir_props(builder.config.root):
            dir_config_extra = dir_config.extra.try_get(
                self.extension_id, WritableDirConfigExtra
            )

            if nn(dir_config_extra) and nn(dir_config.source):
                entity = builder.config.message_sources.sources[
                    dir_config.source.source
                ].entity

                uploaders[dir_config.source.source] = TelegramFileUploader(
                    builder.client, entity
                )

        self._uploaders = writable_extra.uploaders = uploaders

        self.add_sysinfo_items(builder)

    async def extend_vfs_tree_dir(
        self,
        resources: TgmountResources,
        vfs_config: VfsDirConfig,
        tree_dir: VfsTreeDir,
    ):
        dir_config_extra = vfs_config.dir_config.extra.try_get(
            self.extension_id, WritableDirConfigExtra
        )

        writable_resources = resources.extra.try_get(
            self.extension_id, WritableResourcesExtra
        )

        if not nn(writable_resources):
            self.logger.warning(f"Missing WritableResources in extra.")
            return

        if not nn(dir_config_extra):
            return

        if not dir_config_extra.upload:
            return

        if not nn(vfs_config.dir_config.source):
            return

        uploader = writable_resources.uploaders.get(vfs_config.dir_config.source.source)

        if not nn(uploader):
            return

        if not nn(tree_dir.extra):
            tree_dir.extra = Extra()

        extra = tree_dir.extra.create(self.extension_id, VfsDirTreeExtraWritableExtra)

        extra.uploader = uploader
