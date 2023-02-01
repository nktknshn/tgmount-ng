import logging
import os
from typing import AsyncGenerator, Mapping, Sequence, TypeVar, Generator

from tgmount import config, vfs
from tgmount.config.config import ConfigParser
from tgmount.config.config_type import ConfigParserFilter
from tgmount.tgmount.filters_types import FilterConfigValue
from tgmount.util import none_fallback, yes

# from .root_config_reader_props import RootConfigReaderProps
from .root_config_types import RootConfigWalkingContext
from .tgmount_types import TgmountResources
from .vfs_tree_producer_types import VfsTreeProducerConfig, VfsDirConfig
from dataclasses import dataclass
from .logger import module_logger as _logger

T = TypeVar("T")


# @dataclass
# class DirProps:
#     path: list[str]
#     source_prop: RootConfigReaderProps.PropSourceType | None
#     filters_prop: RootConfigReaderProps.PropFilterType | None
#     cache_prop: Mapping | str | None
#     wrappers_prop: Sequence[tuple[str, Mapping | None]] | None
#     producer_prop: tuple[str, Mapping] | None
#     treat_as_prop: list[str] | None
#     other_keys: set[str]
#     raw_config: Mapping


class TgmountConfigReader:
    logger = _logger.getChild("TgmountConfigReader")

    logger.setLevel(logging.ERROR)

    DEFAULT_PRODUCER_NAME = "PlainDir"

    filter_reader: ConfigParserFilter = ConfigParser()

    def __init__(self) -> None:
        pass

    async def get_used_sources(self, dir_config: config.DirConfig) -> set[str]:
        sources = set()
        for dir_props in self.walk_dir_props(dir_config):
            if dir_props.source is None:
                continue

            sources.add(dir_props.source.source)
        return sources

    def walk_dir_props(self, dir_config: config.DirConfig, *, current_path=[]):
        current_path_str = vfs.path_join(*current_path)
        other_keys = set(dir_config.other_keys.keys())

        yield dir_config

        for k, v in dir_config.other_keys.items():
            yield from self.walk_dir_props(v)
        # other_keys = set(d.keys()).difference(self.DIR_PROPS_KEYS)

        # source_prop = self.read_prop_source(d)
        # filters_prop = self.read_prop_filter(d)
        # cache_prop = self.read_prop_cache(d)
        # wrappers_prop = self.read_prop_wrappers(d)
        # producer_prop = self.read_prop_producer(d)
        # treat_as_prop = self.read_prop_treat_as(d)

        # yield DirProps(
        #     current_path,
        #     source_prop,
        #     filters_prop,
        #     cache_prop,
        #     wrappers_prop,
        #     producer_prop,
        #     treat_as_prop,
        #     other_keys,
        #     raw_config=d,
        # )

        # for k in other_keys:
        #     yield from (self.walk_dir_props(d[k], current_path=[*current_path, k]))

    async def walk_config_with_ctx(
        self,
        dir_config: config.DirConfig,
        *,
        resources: TgmountResources,
        ctx: RootConfigWalkingContext,
    ) -> AsyncGenerator[tuple[str, set, VfsDirConfig, RootConfigWalkingContext], None]:
        """Walks `dir_config` instantiating z, yielding a tuple (current path, keys other than current path props, `VfsStructureConfig`, `RootConfigWalkingContext`)"""
        current_path_str = (
            f"/{os.path.join(*ctx.current_path)}" if len(ctx.current_path) > 0 else "/"
        )

        self.logger.info(f"walk_config_with_ctx({current_path_str})")

        other_keys = set(dir_config.other_keys.keys())
        # other_keys = set(dir_config.keys()).difference(self.DIR_PROPS_KEYS)

        source_prop = dir_config.source
        filters_prop = dir_config.filter
        cache_prop = dir_config.cache
        wrappers_prop = dir_config.wrapper
        producer_prop = dir_config.producer
        treat_as_prop = dir_config.treat_as

        # if yes(treat_as_prop):
        factory_prop = {"treat_as": treat_as_prop}

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

        if source_prop is not None and source_prop.recursive is True:
            ctx = ctx.set_recursive_source(
                resources.message_sources[source_prop.source]
            )

        if cache_prop is not None:
            self.logger.info(f"Cache {cache_prop} will be used for files contents")

        if isinstance(cache_prop, config.PropCacheReference):
            current_file_factory = (
                ctx.file_factory
                if cache_prop is None
                else resources.caches.get_filefactory_by_id(cache_prop.cache)
            )
        elif isinstance(cache_prop, config.Cache):
            cached_filefactory = await resources.caches.create_cached_filefactory(
                f"cache-at:{current_path_str}", cache_prop.type, cache_prop.kwargs
            )

            current_file_factory = cached_filefactory

        elif cache_prop is None:
            current_file_factory = ctx.file_factory

        if current_file_factory is None:
            raise config.ConfigError(
                f"Missing cache named {cache_prop} in {ctx.current_path}"
            )

        filters_from_prop = None

        def _parse_filter(filt: FilterConfigValue):
            filters = []
            for filter_name, filter_arg in self.filter_reader.parse_filter_value(filt):
                filter_class = resources.filters_provider.get(filter_name)
                # print(filter_name, filter_class, filter_arg)
                if not yes(filter_class):
                    raise config.ConfigError(
                        f"Missing filter {filter_name} in {ctx.current_path}"
                    )
                filters.append(
                    filter_class.from_config(filter_arg, ctx, _parse_filter),
                )
            return filters

        if yes(filters_prop):
            filters_from_prop = []

            for filter_name, filter_arg in filters_prop.filter:
                filter_class = resources.filters_provider.get(filter_name)
                # print(filter_name, filter_class, filter_arg)
                if not yes(filter_class):
                    raise config.ConfigError(
                        f"Missing filter {filter_name} in {ctx.current_path}"
                    )
                filters_from_prop.append(
                    filter_class.from_config(filter_arg, ctx, _parse_filter)
                )

        # filters_from_prop = (
        #     self.get_filters_from_prop(filters_prop.filter, resources, ctx)
        #     if filters_prop is not None
        #     else None
        # )

        filters_from_ctx = none_fallback(ctx.recursive_filters, [])

        if filters_prop is not None and filters_prop.overwright is True:
            filters = none_fallback(filters_from_prop, [])
        else:
            filters = [*filters_from_ctx, *none_fallback(filters_from_prop, [])]

        """
        the dir will produce content from messages source and applying filter in cases when:
        1. source_prop is specified and it's not recursive
        2. recursive_source is in the context and a filters_prop specified and it's not recursive
        3. source_prop or recursive_source is specified and producer_prop is specified
        4. only producer specified (e.g. for SysInfo producer) 
        """
        if source_prop is not None and not source_prop.recursive:
            self.logger.info(f"1. source_prop is specified and it's not recursive")

            message_source = resources.message_sources.get(source_prop.source)

            if message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop.source} used at {ctx.current_path}"
                )

            if yes(producer_prop):
                producer_name, producer_arg = (
                    producer_prop.producer,
                    producer_prop.kwargs,
                )

        elif (
            ctx.recursive_source is not None
            and filters_prop is not None
            and not filters_prop.recursive
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
                message_source = resources.message_sources.get(source_prop.source)
            else:
                message_source = ctx.recursive_source

            if source_prop is not None and message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop.source} used at {ctx.current_path}"
                )

            producer_name, producer_arg = producer_prop.producer, producer_prop.kwargs

        elif source_prop is not None and source_prop.recursive:
            # if source_prop is recursive update context
            self.logger.info(f"Setting recoursive message source: {source_prop.source}")
            recursive_message_source = resources.message_sources.get(source_prop.source)

            if recursive_message_source is None:
                raise config.ConfigError(
                    f"Missing message source {source_prop.source} used at {ctx.current_path}"
                )
            ctx = ctx.set_recursive_source(recursive_message_source)
        elif yes(producer_prop):
            pass
        elif len(other_keys) == 0:
            pass
            # raise config.ConfigError(
            #     f"Missing source, subfolders or filter in {ctx.current_path}"
            # )

        if yes(filters_prop) and filters_prop.recursive and filters_from_prop:
            self.logger.info(
                f"Setting recursive message filters: {filters_prop.filter}"
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
            for wrapper_name, wrapper_arg in [
                (wrappers_prop.wrapper, wrappers_prop.kwargs)
            ]:
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
                dir_config.other_keys[k],
                resources=resources,
                ctx=ctx.add_path(k),
            ):
                yield t

        # return content_from_source
