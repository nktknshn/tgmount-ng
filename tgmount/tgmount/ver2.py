from typing import Mapping
from tgmount.fs.readable import FileSystemOperationsBase
from tgmount.tgclient import client
from tgmount.tgclient.client_types import TgmountTelegramClientProto
from tgmount.tgclient.message_source_types import MessageSourceProto
from tgmount.tgclient.types import (
    EntityId,
    MessageDeletedEvent,
    MessageEditedEvent,
    MessageReactionEvent,
    NewMessageEvent,
)
from tgmount.tgmount import file_factory
from tgmount.tgmount.extensions.writable import WritableDirConfigExtra
from tgmount.tgmount.file_factory.types import FileFactoryProto
from tgmount.tgmount.vfs_tree_producer_types import (
    VfsDirConfig,
    VfsTreeDirProducerProto,
)
from tgmount.util import nn
from tgmount.vfs import vfs_tree


class Ver2Processor:
    client: TgmountTelegramClientProto
    vfs_tree: vfs_tree.VfsTree
    file_factory: FileFactoryProto
    fs: FileSystemOperationsBase

    message_sources: Mapping[str, MessageSourceProto]
    message_source_by_entity: Mapping[EntityId, list[MessageSourceProto]]
    producer_by_path: Mapping[str, VfsTreeDirProducerProto]
    producer_by_message_source: Mapping[str, MessageSourceProto]
    dir_config_by_path: Mapping[str, VfsDirConfig]

    chat_id_by_entity_id: Mapping[int, EntityId]

    # events from telegram client
    async def on_new_message(self, entity_id: EntityId, event: NewMessageEvent):
        sources = self.message_source_by_entity[entity_id]

    async def on_edited_message(
        self,
        entity_id: EntityId,
        event: MessageEditedEvent | MessageReactionEvent,
    ):
        pass

    async def on_delete_message(self, entity_id: EntityId, event: MessageDeletedEvent):
        pass

    # events from file system
    async def on_create(
        self,
        parent_path: str,
        file_name: str,
    ):
        parent_vfs_config = self.dir_config_by_path[parent_path]
        producer = self.producer_by_path[parent_path]
        parent_dir = await self.vfs_tree.get_dir(parent_path)

        writable_extra = parent_vfs_config.dir_config.extra.get(
            WritableDirConfigExtra,
        )

        if nn(writable_extra) and writable_extra.upload:
            pass

    async def on_unlink(self, dc: VfsDirConfig, parent_path: str, file_name: str):
        parent_dir = await self.vfs_tree.get_dir(parent_path)
