import logging
import os
from typing import AsyncGenerator, Mapping, TypeVar, Generator

from tgmount import config, vfs
from tgmount.util import none_fallback, yes
from .root_config_reader_props import RootProducerPropsReader
from .root_config_types import RootConfigWalkingContext
from .tgmount_types import TgmountResources
from .types import TgmountRootType
from .vfs_tree_producer_types import VfsTreeProducerConfig, VfsDirConfig
from dataclasses import dataclass
from .logger import module_logger as _logger

T = TypeVar("T")


@dataclass
class DirProps:
    path: str
    source_prop: RootProducerPropsReader.PropSourceType | None


class TgmountConfigReader(RootProducerPropsReader):
    logger = _logger.getChild("TgmountConfigReader")

    logger.setLevel(logging.ERROR)

    DEFAULT_PRODUCER_NAME = "PlainDir"

    def __init__(self) -> None:
        pass

    async def get_used_sources(self, d: TgmountRootType) -> set[str]:
        sources = set()
        for dir_props in self.walk_dir_props(d):
            if dir_props.source_prop is None:
                continue

            sources.add(dir_props.source_prop["source_name"])
        return sources

    def walk_dir_props(self, d: TgmountRootType, *, current_path=[]):
        current_path_str = vfs.path_join(*current_path)

        other_keys = set(d.keys()).difference(self.PROPS_KEYS)

        source_prop = self.read_prop_source(d)
        filters_prop = self.read_prop_filter(d)
        cache_prop = self.read_prop_cache(d)
        wrappers_prop = self.read_prop_wrappers(d)
        producer_prop = self.read_prop_producer(d)
        treat_as_prop = self.read_prop_treat_as(d)

        yield DirProps(current_path_str, source_prop)

        for k in other_keys:
            yield from (self.walk_dir_props(d[k], current_path=[*current_path, k]))

    async def walk_config_with_ctx(
        self,
        dir_config: TgmountRootType,
        *,
        resources: TgmountResources,
        ctx: RootConfigWalkingContext,
    ) -> AsyncGenerator[tuple[str, set, VfsDirConfig, RootConfigWalkingContext], None]:
        """Walks `dir_config` yielding a tuple (current path, keys other than current path props, `VfsStructureConfig`, `RootConfigWalkingContext`)"""
        current_path_str = (
            f"/{os.path.join(*ctx.current_path)}" if len(ctx.current_path) > 0 else "/"
        )

        self.logger.info(f"walk_config_with_ctx({current_path_str})")

        other_keys = set(dir_config.keys()).difference(self.PROPS_KEYS)

        source_prop = self.read_prop_source(dir_config)
        filters_prop = self.read_prop_filter(dir_config)
        cache_prop = self.read_prop_cache(dir_config)
        wrappers_prop = self.read_prop_wrappers(dir_config)
        producer_prop = self.read_prop_producer(dir_config)
        factory_prop = self.read_prop_factory(dir_config)
        treat_as_prop = self.read_prop_treat_as(dir_config)

        factory_prop = none_fallback(factory_prop, {})

        if yes(treat_as_prop):
            factory_prop = {**factory_prop, "treat_as": treat_as_prop}

        self.logger.info(f"source_prop={source_prop}")
        self.logger.info(f"filters_prop={filters_prop}")
        self.logger.info(f"producer_prop={producer_prop}")
        self.logger.info(f"wrappers_prop={wrappers_prop}")

        message_source = None
        producer_name = None
        producer_arg = None
        producer = None
        producer_cls = None
        # producer_cls = resources.producers.default
        producer_config = None
        current_file_factory = None

        if source_prop is not None and source_prop["recursive"] is True:
            ctx = ctx.set_recursive_source(
                resources.message_sources[source_prop["source_name"]]
            )

        if cache_prop is not None:
            self.logger.info(f"Cache {cache_prop} will be used for files contents")

        if isinstance(cache_prop, str):
            current_file_factory = (
                ctx.file_factory
                if cache_prop is None
                else resources.caches.get_filefactory_by_id(cache_prop)
            )
        elif isinstance(cache_prop, Mapping):
            cached_filefactory = await resources.caches.create_cached_filefactory(
                f"cache-at:{current_path_str}", cache_prop["type"], cache_prop["kwargs"]
            )

            current_file_factory = cached_filefactory

        elif cache_prop is None:
            current_file_factory = ctx.file_factory

        if current_file_factory is None:
            raise config.ConfigError(
                f"Missing cache named {cache_prop} in {ctx.current_path}"
            )

        filters_from_prop = (
            self.get_filters_from_prop(filters_prop["filters"], resources, ctx)
            if filters_prop is not None
            else None
        )

        filters_from_ctx = none_fallback(ctx.recursive_filters, [])

        if filters_prop is not None and filters_prop["overwright"] is True:
            filters = none_fallback(filters_from_prop, [])
        else:
            filters = [*filters_from_ctx, *none_fallback(filters_from_prop, [])]

        """
        the dir will produce content from messages source and apllying filter in cases when:
        1. source_prop is specified and it's not recursive
        2. recursive_source is in the context and a filters_prop specified and it's not recursive
        3. source_prop or recursive_source is specified and producer_prop is specified
        4. only producer specified (e.g. for SysInfo producer) 
        """
        if source_prop is not None and not source_prop["recursive"]:
            self.logger.info(f"1. source_prop is specified and it's not recursive")

            message_source = resources.message_sources.get(source_prop["source_name"])

            if message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop['source_name']} used at {ctx.current_path}"
                )

        elif (
            ctx.recursive_source is not None
            and filters_prop is not None
            and not filters_prop["recursive"]
            and producer_prop is None
        ):
            self.logger.info(
                f"2. recursive_source is in the context and a filters_prop specified: {filters_prop}"
            )
            message_source = ctx.recursive_source
        elif (
            source_prop is not None or ctx.recursive_source is not None
        ) and producer_prop is not None:
            self.logger.info(
                f"3. source_prop or recursive_source is specified and producer_prop is specified: {producer_prop}"
            )

            if source_prop is not None:
                message_source = resources.message_sources.get(
                    source_prop["source_name"]
                )
            else:
                message_source = ctx.recursive_source

            if source_prop is not None and message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop['source_name']} used at {ctx.current_path}"
                )

            producer_name, producer_arg = producer_prop

        elif source_prop is not None and source_prop["recursive"]:
            # if source_prop is recursive update context
            self.logger.info(
                f"Setting recoursive message source: {source_prop['source_name']}"
            )
            recursive_message_source = resources.message_sources.get(
                source_prop["source_name"]
            )

            if recursive_message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop['source_name']} used at {ctx.current_path}"
                )
            ctx = ctx.set_recursive_source(recursive_message_source)
        elif yes(producer_prop):
            pass
        elif len(other_keys) == 0:
            raise config.ConfigError(
                f"Missing source, subfolders or filter in {ctx.current_path}"
            )

        if yes(filters_prop) and filters_prop["recursive"] and filters_from_prop:
            self.logger.info(
                f"Setting recoursive message filters: {filters_prop['filters']}"
            )
            ctx = ctx.extend_recursive_filters(filters_from_prop)

        if message_source is not None:
            self.logger.info(f"The folder will be containing files")

            # if producer_name is not None:
            producer_name = none_fallback(producer_name, self.DEFAULT_PRODUCER_NAME)

            self.logger.info(f"Content will be produced by {producer_name}")

            producer_cls = resources.producers.get_by_name(producer_name)

            # producer_cls = resources.producers.get_producers().get(producer_name)

            if producer_cls is None:
                raise config.ConfigError(
                    f"Missing producer: {producer_name}. path: {ctx.current_path}"
                )

        vfs_wrappers = []

        if wrappers_prop is not None:
            for wrapper_name, wrapper_arg in wrappers_prop:
                wrapper_cls = resources.vfs_wrappers.get_by_name(wrapper_name)

                if wrapper_cls is None:
                    raise config.ConfigError(
                        f"Missing wrapper: {wrapper_name}. path: {ctx.current_path}"
                    )

                vfs_wrappers.append((wrapper_cls, wrapper_arg))

        if message_source is not None:
            producer_config = VfsTreeProducerConfig(
                message_source=message_source,
                factory=current_file_factory,
                filters=filters,
                factory_props=factory_prop,
            )

        vfs_config = VfsDirConfig(
            dir_config=dir_config,
            vfs_producer=producer_cls,
            vfs_producer_arg=producer_arg,
            vfs_wrappers=vfs_wrappers,
            vfs_producer_config=producer_config,
        )

        yield (current_path_str, other_keys, vfs_config, ctx)

        for k in other_keys:
            async for t in self.walk_config_with_ctx(
                dir_config[k],
                resources=resources,
                ctx=ctx.add_path(k),
            ):
                yield t

        # return content_from_source
