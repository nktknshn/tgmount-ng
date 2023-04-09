from dataclasses import dataclass
from typing import Optional, Iterable, Type, Protocol

from typing import Mapping
from abc import abstractmethod
from tgmount.tgclient import MessageSourceProto
from tgmount.tgclient.message_types import MessageProto
from tgmount.tgmount.file_factory import FileFactoryProto
from tgmount.tgmount.filters_types import Filter
from tgmount import config

# XXX circular import
# from tgmount.tgmount.tgmount_resources import TgmountResources
from tgmount.vfs.vfs_tree import VfsTreeDir
from tgmount.vfs.vfs_tree_wrapper_types import VfsTreeWrapperProto


class VfsTreeDirProducerConfig:
    """Wraps `message_source` with other"""

    message_source: MessageSourceProto
    factory: FileFactoryProto
    filters: list[Filter]
    factory_props: Mapping | None = None

    def __init__(
        self,
        message_source: MessageSourceProto,
        factory: FileFactoryProto,
        filters: list[Filter],
        factory_props: Mapping | None = None,
    ) -> None:
        self.message_source = message_source
        self.factory = factory
        self.filters = filters
        self.factory_props = factory_props

        self._messages: list[MessageProto] | None = None

    async def produce_file(self, m: MessageProto):
        """Using the file factory produce a file from a message"""
        return await self.factory.file(m, factory_props=self.factory_props)

    async def apply_filters(
        self, messages: Iterable[MessageProto]
    ) -> list[MessageProto]:
        """Applies filters from config to the messages sequence"""
        messages = list(messages)

        for f in self.filters:
            messages = await f.filter(messages)

        return messages

    async def get_messages(self) -> list[MessageProto]:
        """Get messages list from message_source filtered with the filters
        from config"""
        messages = await self.message_source.get_messages()

        if self._messages is None:
            self._messages = await self.apply_filters(messages)

        return self._messages

    def set_message_source(self, message_source: MessageSourceProto):
        return VfsTreeDirProducerConfig(
            message_source=message_source,
            factory=self.factory,
            filters=self.filters,
            factory_props=self.factory_props,
        )


@dataclass
class VfsDirConfig:
    """Contains information to create a `VfsTreeDirProducer`"""

    dir_config: config.DirConfig
    """ Config this structure was sourced from """

    vfs_producer: Type["VfsTreeDirProducerProto"] | None
    """ Producer for a vfs structure content """

    vfs_producer_arg: Optional[Mapping] = None
    """ Producer constructor argument """

    vfs_producer_config: Optional[VfsTreeDirProducerConfig] = None

    vfs_wrappers: Optional[
        list[tuple[Type[VfsTreeWrapperProto], Optional[Mapping]]]
    ] = None
    # vfs_wrapper_arg: Optional[Type[Mapping]] = None


class VfsTreeDirProducerProto(Protocol):
    @abstractmethod
    async def produce(self) -> None:
        ...

    @classmethod
    @abstractmethod
    async def from_config(
        cls,
        resources,
        config: VfsTreeDirProducerConfig,
        arg: Mapping,
        dir: VfsTreeDir,
        # dir: VfsTreeDir,
        # XXX
    ) -> "VfsTreeDirProducerProto":
        ...


class VfsTreeProducerExtensionProto(Protocol):
    async def extend_vfs_tree_dir(
        self,
        # resources: TgmountResources,
        resources,
        vfs_config: VfsDirConfig,
        tree_dir: VfsTreeDir,
    ):
        pass
