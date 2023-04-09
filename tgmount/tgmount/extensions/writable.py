import functools
from typing import ClassVar, Mapping, Protocol

from telethon import events

from tgmount import config, fs, vfs
from tgmount.common.extra import Extra
from tgmount.config import ConfigExtensions, DirConfigReader, PropertyReader
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tgmount.extensions.types import TgmountExtensionProto
from tgmount.tgmount.file_factory.filefactory import (
    FileFactoryDefault,
    TelegramFileExtra,
)
from tgmount.tgmount.file_factory.types import FileFactoryProto
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
    DirContentCanCreateProto,
    FileContentWritableConsumer,
    VfsTree,
    VfsTreeDir,
    VfsTreeDirContent,
)
from tgmount.vfs.types.dir import DirContentCanRemoveProto
from tgmount.vfs.vfs_tree import VfsTreeDirContentProto

from .logger import logger

logger = logger.getChild(f"writable")


class VfsDirTreeExtraWritableExtra:
    extra_name: ClassVar[str] = "writable"
    uploader: TelegramFileUploader | None


class WritableDirConfigExtra(Protocol):
    extra_name: ClassVar[str] = "writable"
    upload: bool | None


class WritableResourcesExtra(Protocol):
    extra_name: ClassVar[str] = "writable"
    uploaders: Mapping[str, TelegramFileUploader]


class VfsTreeWritable(VfsTree):
    def __init__(self, file_factory: FileFactoryProto) -> None:
        super().__init__()
        self._file_factory = file_factory

    async def get_dir_content(self, path: str = "/") -> VfsTreeDirContent:
        """if the folder has extra with uploader"""
        d = await self.get_dir(path)

        writable_extra = map_none(
            d.extra,
            lambda e: e.get(VfsDirTreeExtraWritableExtra),
        )

        if nn(writable_extra) and nn(writable_extra.uploader):
            return VfsTreeDirContentWritable(
                self, path, writable_extra.uploader, self._file_factory
            )

        return await super().get_dir_content(path)


class VfsTreeDirContentCanUpload(
    VfsTreeDirContentProto,
    DirContentCanCreateProto,
):
    logger = logger.getChild("VfsTreeDirContentCanUpload")

    # events_dispatcher: TelegramEventsDispatcher
    def __init__(
        self,
        uploader: TelegramFileUploader,
        file_factory: FileFactoryProto,
    ) -> None:
        self._logger = VfsTreeDirContentCanUpload.logger.getChild(
            self.path, suffix_as_tag=True
        )

        self._uploader = uploader
        self._file_factory = file_factory
        self._uploading_files: dict[str, vfs.FileLike] = {}
        self._uploading_progress: dict[str, int] = {}

    async def create(self, filename: str) -> vfs.FileLike:
        logger.debug(f"create({filename})")

        vfs_dir = await self.vfs_dir

        filelike = await self._create_filelike(filename)

        # we don't need to notify the fs since it already knows about the file
        await vfs_dir.put_content([filelike], notify=False)

        self._uploading_files[filename] = filelike
        return filelike

    async def on_complete(self, filename: str, message: MessageDownloadable):
        # vfs_dir = await self.vfs_dir
        # or recreate it using file factory and update the file
        await self._remove_file(filename)
        # filelike = await self._file_factory.file(message, filename)

        # await vfs_dir.update_content({filename: filelike})

    async def on_error(self, filename: str, error: Exception):
        await self._remove_file(filename)

    async def _remove_file(self, filename: str):
        thedir = await self.vfs_dir
        await thedir.remove_content(self._uploading_files[filename])
        del self._uploading_files[filename]

    async def _create_filelike(self, filename: str) -> vfs.FileLike:
        content = FileContentWritableConsumer.on_close(
            on_close=functools.partial(self._upload, filename)
        )
        return vfs.FileLike(filename, content=content)

    async def _upload(self, filename: str, data: bytes):
        try:
            msg = await self._uploader.upload(
                data,
                file_name=filename,
                file_size=len(data),
                notify=False,
            )
            await self.on_complete(filename, msg)
        except Exception as e:
            self._logger.error(f"Error uploading file {filename}")
            await self.on_error(filename, e)


class VfsTreeDirContentCanRemove(VfsTreeDirContentProto, DirContentCanRemoveProto):
    """Extension for VfsTreeDirContentProto"""

    logger = logger.getChild("VfsTreeDirContentCanRemove")

    def __init__(self, uploader: TelegramFileUploader) -> None:
        self._logger = VfsTreeDirContentCanRemove.logger.getChild(
            self.path, suffix_as_tag=True
        )

        self._uploader = uploader

    async def remove(self, file_name: str):
        self._logger.debug(f"remove({file_name})")

        thedir = await self.tree.get_dir(self.path)
        item = await thedir.get_by_name(file_name)

        if nn(item):
            await thedir.remove_content(item)

            if nn(message_extra := item.extra.try_get(TelegramFileExtra)):
                # XXX how to catch
                await self._uploader.remove([message_extra.message_id])
            else:
                self._logger.error(
                    f"Missing message information in the file extra in {file_name}."
                )
        else:
            self._logger.error(
                f"remove({file_name}). Item with the name was not found in "
                "the folder."
            )


class VfsTreeDirContentWritable(
    VfsTreeDirContent,
    VfsTreeDirContentCanRemove,
    VfsTreeDirContentCanUpload,
):
    """DirContent with methods `create` and `remove`"""

    def __init__(
        self,
        tree: "VfsTree",
        path: str,
        uploader: TelegramFileUploader,
        file_factory: FileFactoryProto,
    ) -> None:
        VfsTreeDirContent.__init__(self, tree, path)
        VfsTreeDirContentCanRemove.__init__(self, uploader)
        VfsTreeDirContentCanUpload.__init__(self, uploader, file_factory)


class TgmountExtensionWritable(TgmountExtensionProto):
    extension_id = "writable"

    VfsTree = VfsTreeWritable
    # FileSystemOperations = fs.FileSystemOperations

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

    async def extend_tgmount(
        self,
        builder: TgmountBuilderBase,
        tgmount: TgmountBase,
    ):
        for uploader in self._uploaders.values():
            # Because changes that are made through the client will not trigger
            # events we have to do it manually
            uploader.on_uploaded.subscribe(
                lambda sender, msg: tgmount.on_new_message(
                    uploader._entity, events.NewMessage.Event(msg)
                )
            )

    async def create_vfs_tree(self, builder: TgmountBuilderBase):
        return VfsTreeWritable(builder.resources.file_factory)

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

        for dir_config in TgmountRootConfigWalker().walk_dir_props(
            builder.config.root,
        ):
            dir_config_extra = dir_config.extra.try_get(WritableDirConfigExtra)

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
            WritableDirConfigExtra,
        )

        writable_resources = resources.extra.try_get(WritableResourcesExtra)

        if not nn(writable_resources):
            self.logger.warning(f"Missing WritableResources in extra.")
            return

        if not nn(dir_config_extra):
            return

        if not dir_config_extra.upload:
            return

        if not nn(vfs_config.dir_config.source):
            return

        uploader = writable_resources.uploaders.get(
            vfs_config.dir_config.source.source,
        )

        if not nn(uploader):
            return

        if not nn(tree_dir.extra):
            tree_dir.extra = Extra()

        extra = tree_dir.extra.create(
            self.extension_id,
            VfsDirTreeExtraWritableExtra,
        )

        extra.uploader = uploader


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
