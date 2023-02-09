from abc import abstractmethod
from typing import Protocol, Type
from tgmount import fs, config
from tgmount.config.reader import TgmountConfigExtensionProto
from tgmount.tgmount.types import TgmountBuilderExtensionProto

from tgmount.tgmount.vfs_tree_producer_types import (
    VfsTreeProducerExtensionProto,
)
from tgmount.tgmount.vfs_tree import VfsTree


class VfsTreeExtensionProto(Protocol):
    VfsTree: Type[VfsTree] | None
    FileSystemOperations: Type[fs.FileSystemOperations] | None


class TgmountExtensionProto(
    TgmountConfigExtensionProto,
    TgmountBuilderExtensionProto,
    VfsTreeProducerExtensionProto,
    VfsTreeExtensionProto,
    Protocol,
):
    @abstractmethod
    async def extend_tgmount(
        self,
        # cfg: config.Config,
        # builder: TgmountBuilderBase,
        # resources: TgmountResources,
        # tgmount: TgmountBase,
        cfg: config.Config,
        builder,
        resources,
        tgmount,
    ):
        pass
