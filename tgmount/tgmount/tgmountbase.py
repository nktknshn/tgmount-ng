import abc
import os
from typing import Mapping, Optional, Type

from telethon import events

from tgmount import main, tgclient, tglog, vfs, config
from tgmount.common.extra import Extra
from tgmount.fs.update import FileSystemOperationsUpdate, FileSystemOperationsUpdatable
from tgmount.tgclient.events_dispatcher import TelegramEventsDispatcher
from tgmount.tgclient.message_reaction_event import MessageReaction
from tgmount.tgclient.message_types import MessageProto
from tgmount.tgclient.types import (
    EntityId,
    MessageDeletedEvent,
    MessageEditedEvent,
    MessageReactionEvent,
    NewMessageEvent,
)
from tgmount.tgmount.vfs_tree_producer import VfsTree, VfsTreeProducer
from tgmount.util import none_fallback
from tgmount.util.timer import measure_time
from tgmount.util.lock import Lock

from tgmount.error import TgmountError
from .logger import module_logger as _logger
from .tgmount_resources import TgmountResources
from tgmount.vfs.vfs_tree import TreeListener, VfsTreeDir
from tgmount.vfs import vfs_tree_types as tree_event


class TgmountBase:
    """
    Wraps the application state and all the async initialization, connects
    all the app parts together

    Connects VfsTree and FilesystemOperations by dispatching events from
    the virtual tree to FilesystemOperations
    """

    logger = _logger.getChild("TgmountBase")

    def __init__(
        self,
        *,
        client: tgclient.client_types.TgmountTelegramClientReaderProto,
        resources: TgmountResources,
        root_config: config.DirConfig,
        fs: FileSystemOperationsUpdatable,
        vfs_tree: VfsTree,
        vfs_tree_producer: VfsTreeProducer,
        events_dispatcher: TelegramEventsDispatcher,
        mount_dir: Optional[str] = None,
    ) -> None:
        # must be initialized by TgmountBuilder
        self._fs: FileSystemOperationsUpdatable = fs
        self._vfs_tree: VfsTree = vfs_tree
        self._producer: VfsTreeProducer = vfs_tree_producer
        self._events_dispatcher: TelegramEventsDispatcher = events_dispatcher

        self._client = client
        self._root_config = root_config
        self._resources = resources
        self._mount_dir: Optional[str] = mount_dir

        """ Ensures that changes are atomic """
        self._update_lock = Lock("TgmountBase._update_lock", self.logger, tglog.TRACE)

    # region properties
    @property
    def fs(self):
        return self._fs

    @fs.setter
    def fs(self, fs: FileSystemOperationsUpdatable):
        self._fs = fs

    @property
    def extra(self) -> Extra:
        return self._resources.extra

    @property
    def vfs_tree(self) -> VfsTree:
        return self._vfs_tree

    @vfs_tree.setter
    def vfs_tree(self, vfs_tree: VfsTree):
        self._vfs_tree = vfs_tree

    @property
    def resources(self) -> TgmountResources:
        return self._resources

    @property
    def events_dispatcher(self) -> TelegramEventsDispatcher:
        return self._events_dispatcher

    @events_dispatcher.setter
    def events_dispatcher(self, ed: TelegramEventsDispatcher):
        self._events_dispatcher = ed

    @property
    def producer(self) -> VfsTreeProducer:
        return self._producer

    @producer.setter
    def producer(self, producer: VfsTreeProducer):
        self._producer = producer

    @property
    def client(self):
        return self._client

    # endregion

    async def fetch_messages(self):
        """Fetches initial messages lists from message_sources"""

        self.logger.info(
            f"Fetching initial messages from "
            f"({list(self.resources.fetchers.keys())})..."
        )

        for k, fetcher in self.resources.fetchers.items():
            self.logger.info(f"Fetching from '{k}'...")
            source = self.resources.message_sources.get(k)

            assert source

            initial_messages = await fetcher.fetch()

            self.logger.info(f"Fetched {len(initial_messages)} messages.")

            await source.set_messages(initial_messages, notify=False)

        self.logger.info(f"Done fetching.")

    async def resume_dispatcher(self):
        await self.events_dispatcher.resume()

    """ 
    - TgmountBase subscribed to client updates
    - TelegramClient receives an event
    - TgmountBase receives an event
        - Update lock here
    - TgmountBase passes event to TelegramEventsDispatcher and starts exclusive 
        listening for events from VfsTree. (User actions may also generate events 
        concurrently and they will be caught).
    - TelegramEventsDispatcher, if not paused (it is paused during initial 
        messages fetching), turns events into calls to MessageSources update methods
        (add_message, remove_message or edit_message).
    - MessageSource filters incoming messages with the attached filters.
    - MessageSource updates containing messages list (adds or removes messages or 
    updates the list depending on the event type).
    - MessageSource notifies the subscribed VfsTreeDirProducers with the messages.
    - VfsTreeDirProducer updates the VfsTreeDir which it is responsible for.
        - VfsTreeDirProducer has access to tgmount resources like file_factory.
        - VfsTreeDirProducer removes vfs item from the directory or creates new
            files by the file factory
    - This generates events (TreeEventType) from VfsTree
    - TgmountBase receives them turning into FileOperations update and passing to it
    - FileOperations process update, updating inodes etc
        - Update unlock here

    - User does something in the mounted filesystem
    - a FileOperations method called
    - FileOperations calls a method of a FileLike or a DirLike
    - FileLike or a DirLike methods update VfsTree
    - VfsTree generates `TreeEventType`
    - TgmountBase receives them turning into `FileSystemOperationsUpdate`
    """

    # region events handlers
    @measure_time(logger_func=logger.info)
    async def on_new_message(
        self,
        entity_id: EntityId,
        event: NewMessageEvent,
    ):
        self.logger.info(
            f"on_new_message({entity_id}, {MessageProto.repr_short(event.message)})"
        )
        self.logger.trace(f"on_new_message({event})")

        async with self._update_lock:
            listener = TreeListener(self._vfs_tree, exclusively=True)

            async with listener:
                await self.events_dispatcher.process_new_message_event(entity_id, event)

            if len(listener.events) > 0:
                self.logger.debug(f"Tree generated {len(listener.events)} events")
                await self._dispatch_tree_events_to_filesystem(listener.events)

        # self.logger.info(f"on_new_message() done")

    @measure_time(logger_func=logger.info)
    async def on_delete_message(self, entity_id: EntityId, event: MessageDeletedEvent):
        self.logger.info(f"on_delete_message({entity_id}, {event.deleted_ids})")
        listener = TreeListener(self._vfs_tree, exclusively=True)

        async with self._update_lock:
            async with listener:
                await self.events_dispatcher.process_delete_message_event(
                    entity_id, event
                )

            if len(listener.events) > 0:
                self.logger.debug(f"Tree generated {len(listener.events)} events")
                await self._dispatch_tree_events_to_filesystem(listener.events)

        # self.logger.info(f"on_delete_message() done")

    @measure_time(logger_func=logger.info)
    async def on_edited_message(
        self,
        entity_id: EntityId,
        event: MessageEditedEvent | MessageReactionEvent,
    ):
        if isinstance(event, events.MessageEdited.Event):
            self.logger.info(
                f"on_edited_message({entity_id}, "
                f"{MessageProto.repr_short(event.message)})"
            )
        else:
            self.logger.info(
                f"on_edited_message({entity_id}, reaction update for "
                f"message {event.msg_id})"
            )

        self.logger.trace(event)

        listener = TreeListener(self._vfs_tree, exclusively=True)

        async with self._update_lock:
            async with listener:
                try:
                    await self.events_dispatcher.process_edited_message_event(
                        entity_id, event
                    )
                except Exception as e:
                    self.logger.error(e)

            if len(listener.events) > 0:
                self.logger.debug(f"Tree generated {len(listener.events)} events")
                await self._dispatch_tree_events_to_filesystem(listener.events)

    async def on_event_from_fs(self, s, updates: list[tree_event.TreeEventType]):
        """Called when a user action like create or unlink triggers changes
        in VfsTree
        """
        self.logger.debug(f"on_event_from_fs({updates})")

        async with self._update_lock:
            if self.fs.initialized:
                await self._dispatch_tree_events_to_filesystem(updates)
            else:
                self.logger.warning(f"FileSystem is not initialized yet")

    # endregion

    async def produce_vfs_tree(self):
        """Produce VfsTree"""

        self.logger.info(f"Producing VfsTree.")

        await self._producer.produce(
            self.resources,
            self._root_config,
            self.vfs_tree,
        )

    async def _get_dir_content(self, path: str) -> vfs.DirContentProto:
        return await self._vfs_tree.get_dir_content(path)
        # d = await self.vfs_tree.get_dir(path)

    async def create_fs(self):
        """Produce VfsTree and init `FileSystemOperations` with it"""

        await self.produce_vfs_tree()

        self.fs.init_root(await self._get_dir_content("/"))

    async def _dispatch_tree_events_to_filesystem(
        self, events: list[tree_event.TreeEventType[VfsTreeDir]]
    ):
        if not self.fs.initialized:
            self.logger.error(f"fs is not initialized yet.")
            return

        if len(events) == 0:
            return

        for e in events:
            fs_update = FileSystemOperationsUpdate()

            if isinstance(e, tree_event.TreeEventRemovedItems):
                path = e.sender.path

                for item in e.removed_items:
                    fs_update.removed_files.append(os.path.join(path, item.name))

            elif isinstance(e, tree_event.TreeEventNewItems):
                path = e.sender.path

                for item in e.new_items:
                    if isinstance(item, vfs.FileLike):
                        fs_update.new_files[os.path.join(path, item.name)] = item
                    else:
                        fs_update.new_dirs[os.path.join(path, item.name)] = item

            elif isinstance(e, tree_event.TreeEventRemovedDirs):
                for path in e.removed_dirs:
                    fs_update.removed_dirs.append(path)

            elif isinstance(e, tree_event.TreeEventUpdatedItems):
                for path, item in e.updated_items.items():
                    fs_update.update_items[path] = item

            elif isinstance(e, tree_event.TreeEventNewDirs):
                for path in e.new_dirs:
                    fs_update.new_dirs[path] = await self._get_dir_content(path)

            async with self.fs._update_lock:
                await self.fs.update(fs_update)

    async def mount(
        self,
        *,
        mount_dir: Optional[str] = None,
        debug_fuse=False,
        min_tasks=10,
    ):
        """Mount process consists of two phases: fetching messages and building
        vfs root"""

        mount_dir = none_fallback(mount_dir, self._mount_dir)

        if mount_dir is None:
            raise TgmountError(f"Missing mount destination.")

        # self.logger.info(f"Building...")

        assert self.events_dispatcher.is_paused

        # fetch initial messages
        await self.fetch_messages()

        # create
        await self.create_fs()

        # pass updates that has been received during previous stages
        await self.events_dispatcher.resume()

        self.logger.info(f"Mounting into {mount_dir}")

        await main.util.mount_ops(
            self._fs,
            mount_dir=mount_dir,
            min_tasks=min_tasks,
            debug=debug_fuse,
        )
