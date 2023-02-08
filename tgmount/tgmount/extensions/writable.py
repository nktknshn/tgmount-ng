from abc import abstractmethod
from typing import Mapping, Protocol
from tgmount import config
from tgmount.common.extra import Extra
from tgmount.config.config import DirConfigReader
from tgmount.config.reader import TgmountConfigExtensionProto
from tgmount.tgclient import uploader
from tgmount.tgmount.tgmount_builderbase import (
    TgmountBuilderBase,
    TgmountBuilderExtensionProto,
)
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.tgmount.vfs_tree import VfsTree, VfsTreeDir
from tgmount.tgmount.vfs_tree_producer_types import VfsDirConfig

from tgmount.util import no, yes
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tgmount.root_config_reader import TgmountConfigReader


class VfsDirTreeExtraWritable:
    uploader: TelegramFileUploader | None


class WritableDirConfig(Protocol):
    upload: bool | None


class WritableResources(Protocol):
    uploaders: Mapping[str, TelegramFileUploader]


class TgmountVfsTreeProducerExtension(Protocol):
    @abstractmethod
    async def extend_vfs_tree_dir(
        self,
        resources: TgmountResources,
        vfs_config: VfsDirConfig,
        tree_dir: VfsTreeDir,
    ):
        ...


class TgmountExtensionWritable(
    TgmountConfigExtensionProto,
    TgmountBuilderExtensionProto,
    TgmountVfsTreeProducerExtension,
):
    prop = "writable"

    def extend_config(self, reader: DirConfigReader, extra: Extra):
        extra.create(self.prop)
        extra.writable.upload = reader.boolean("upload")

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

        extra.uploaders = uploaders

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
