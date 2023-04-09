import abc
from dataclasses import replace
from typing import Protocol, Type

from tgmount import config, fs, tgclient
from tgmount.common.extra import Extra
from tgmount.error import TgmountError
from tgmount.tgclient.events_dispatcher import TelegramEventsDispatcher
from tgmount.tgclient.fetcher import TelegramMessagesFetcher
from tgmount.tgclient.source.util import BLOCK_SIZE
from tgmount.tgmount.cached_filefactory_factory import CacheFileFactoryFactory
from tgmount.tgmount.extensions.types import TgmountExtensionProto
from tgmount.tgmount.producers.producer_sysinfo import VfsTreeProducerSysInfo
from tgmount.tgmount.providers.provider_vfs_wrappers import ProviderVfsWrappersBase
from tgmount.tgmount.root_config_walker import TgmountRootConfigWalker
from tgmount.tgmount.vfs_tree_producer import VfsTreeProducer
from tgmount.util import get_bytes_count, none_fallback, nn
from tgmount.vfs.vfs_tree import VfsTree

from .file_factory import FileFactoryDefault, classifier
from .logger import module_logger as logger
from .providers.provider_caches import CachesTypesProviderProto
from .providers.provider_filters import FilterProviderProto
from .providers.provider_producers import ProducersProviderBase
from .providers.provider_sources import SourcesProvider
from .tgmount_resources import TgmountResources
from .tgmountbase import TgmountBase


class TgmountBuilderBase(abc.ABC):
    """Constructs TgmountBase from a config"""

    logger = logger.getChild(f"TgmountBuilderBase")

    TelegramClient: Type[tgclient.client_types.TgmountTelegramClientProto]
    MessageSource: Type[tgclient.MessageSource]
    FilesSource: Type[tgclient.TelegramFilesSource]
    FileFactory: Type[FileFactoryDefault]
    CacheFactory: Type[CacheFileFactoryFactory]

    TgmountBase = TgmountBase
    TelegramMessagesFetcher = TelegramMessagesFetcher
    TelegramEventsDispatcher = TelegramEventsDispatcher
    VfsTree = VfsTree
    VfsTreeProducer = VfsTreeProducer

    FileSystemOperations: Type[fs.FileSystemOperations] = fs.FileSystemOperations

    classifier: classifier.ClassifierBase
    caches: CachesTypesProviderProto
    filters: FilterProviderProto
    wrappers: ProviderVfsWrappersBase
    producers: ProducersProviderBase

    extensions: list[TgmountExtensionProto] = []

    async def create_client(self, cfg: config.Config, **kwargs):
        return self.TelegramClient(
            cfg.client.session,
            cfg.client.api_id,
            cfg.client.api_hash,
            use_ipv6=cfg.client.use_ipv6,
            **kwargs,
        )

    async def create_vfs_tree(self):
        for ext in self.extensions:
            vfs_tree = await ext.create_vfs_tree(self)
            if nn(vfs_tree):
                return vfs_tree
            # if nn(ext.VfsTree):
            #     return ext.VfsTree()

        return self.VfsTree()

    async def create_file_source(self, cfg: config.Config, client):
        return self.FilesSource(
            client,
            request_size=get_bytes_count(
                none_fallback(cfg.client.request_size, BLOCK_SIZE)
            ),
        )

    async def create_file_factory(self, cfg: config.Config, client, files_source):
        return self.FileFactory(files_source)

    async def create_cached_filefactory_factory(self, cfg: config.Config, client):
        self.cached_filefactory_factory = self.CacheFactory(
            client,
            self.caches,
            files_source_request_size=get_bytes_count(
                none_fallback(cfg.client.request_size, BLOCK_SIZE)
            ),
        )
        return self.cached_filefactory_factory

    async def create_events_dispatcher(self, cfg: config.Config, client):
        return self.TelegramEventsDispatcher()

    async def create_message_source(
        self, cfg: config.Config, client, msc: config.MessageSource
    ):
        return self.MessageSource(tag=msc.entity)

    async def create_fetcher(
        self,
        cfg: config.Config,
        client,
        msc: config.MessageSource,
        message_source,
    ):
        return self.TelegramMessagesFetcher(client, msc)

    async def create_tgmount_resources(self):
        config = self.config
        client = self.client

        sources_used_in_root = await TgmountRootConfigWalker().get_used_sources(
            config.root
        )

        files_source = await self.create_file_source(config, client)
        file_factory = await self.create_file_factory(config, client, files_source)

        source_provider = SourcesProvider()

        fetchers_dict = {}

        for k, msc in config.message_sources.sources.items():
            if k not in list(sources_used_in_root):
                continue

            message_source = await self.create_message_source(config, client, msc)

            message_source.add_filter(file_factory.supports)

            if nn(msc.filter):
                tg_filter = self.filters.telegram_filters.get(msc.filter)

                if nn(tg_filter):
                    message_source.add_filter(tg_filter())

            fetcher = await self.create_fetcher(config, client, msc, message_source)

            fetchers_dict[k] = fetcher

            source_provider.add_source(k, message_source)

        cached_filefactory_factory = await self.create_cached_filefactory_factory(
            config, client
        )

        caches_config = config.caches.caches if config.caches is not None else {}

        for cache_id, cache_config in caches_config.items():
            await self.cached_filefactory_factory.create_cached_filefactory(
                cache_id, cache_config.type, cache_config.kwargs
            )

        resources = TgmountResources(
            message_sources=source_provider,
            fetchers=fetchers_dict,
            caches=cached_filefactory_factory,
            file_factory=file_factory,
            filters_provider=self.filters,
            producers=self.producers,
            classifier=self.classifier,
            vfs_wrappers=self.wrappers,
            extra=Extra(),
        )

        return resources

    async def extend_resources_extra(self):
        VfsTreeProducerSysInfo.create_sysinfo_extra(
            self.resources.extra, self.resources, self.tgm.fs
        )

        for ext in self.extensions:
            await ext.extend_resources(self)

    async def create_filesystem_operations(self):
        # for ext in self.extensions:
        #     if yes(ext.FileSystemOperations):
        #         return ext.FileSystemOperations(None)

        return self.FileSystemOperations(None)

    async def create_vfs_tree_producer(self) -> VfsTreeProducer:
        return self.VfsTreeProducer(extensions=self.extensions)

    async def create_tgmountbase(self):
        vfs_tree_producer = await self.create_vfs_tree_producer()
        vfs_tree = await self.create_vfs_tree()
        events_dispatcher = self.TelegramEventsDispatcher()
        fs = await self.create_filesystem_operations()

        return self.TgmountBase(
            client=self.client,
            resources=self.resources,
            root_config=self.config.root,
            mount_dir=self.config.mount_dir,
            fs=fs,
            vfs_tree=vfs_tree,
            vfs_tree_producer=vfs_tree_producer,
            events_dispatcher=events_dispatcher,
        )

    async def create_tgmount(self, cfg: config.Config, **kwargs) -> TgmountBase:
        self.config = cfg
        self.client = await self.create_client(cfg, **kwargs)
        self.resources = await self.create_tgmount_resources()
        self.tgm = tgm = await self.create_tgmountbase()

        await self.extend_resources_extra()

        # subscribe for the events that are triggered by file system
        # like upload or file remove
        tgm.vfs_tree.subscribe(tgm.on_event_from_fs)

        # subscribe tgm
        for k, msc in cfg.message_sources.sources.items():
            ms = self.resources.message_sources.get(k)

            if ms is None:
                # message source hasn't been used in root config
                continue

            updates = none_fallback(msc.updates, True)

            if not updates:
                continue

            self.client.subscribe_new_messages(
                lambda ev, eid=msc.entity: tgm.on_new_message(eid, ev), chats=msc.entity
            )
            self.client.subscribe_removed_messages(
                lambda ev, eid=msc.entity: tgm.on_delete_message(eid, ev),
                chats=msc.entity,
            )
            self.client.subscribe_edited_message(
                lambda ev, eid=msc.entity: tgm.on_edited_message(eid, ev),
                chats=msc.entity,
            )

            tgm.events_dispatcher.connect(msc.entity, ms)

        for ext in self.extensions:
            await ext.extend_tgmount(cfg, tgm)

        return tgm
