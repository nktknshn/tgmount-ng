from typing import Any, TypeVar
from tgmount import config
from tgmount.config.config_type import ConfigParserFilter, ConfigParserProto
from tgmount.config.types import FilterConfigValue, FilterInputType

from tgmount.util import get_bytes_count, map_none, no
from tgmount.util.col import get_first_pair


from .logger import logger
from collections.abc import Mapping
from .reader import PropertyReader, ConfigContext

T = TypeVar("T")


def ensure_list(value: T | list[T]) -> list[T]:
    if isinstance(value, list):
        return value

    return [value]


class FilterPropReader(PropertyReader):
    def __init__(self, ctx: "ConfigContext") -> None:
        super().__init__(ctx)

    @property
    def klass(self):
        return FilterPropReader

    def parse_filter_value_item(self, value: Any) -> tuple[str, Any]:
        t = self.typeof_value(value)

        if t == "string":
            return (value, None)
        elif t == "mapping":
            self.ctx.assert_that(
                len(value) == 1, "Filter is a mapping with one key or a string"
            )
            return get_first_pair(value)
        else:
            self.ctx.fail(f"Invalid filter value item: {value}")

    def parse_filter_value(self, value: Any) -> FilterInputType:
        t = self.typeof_value(value)

        if t == "string" or t == "mapping":
            return [self.parse_filter_value_item(value)]
        elif t == "list":
            result = []
            for idx, el in enumerate(value):
                result.append(
                    self.add_path(str(idx)).parse_filter_value_item(el),
                )
            return result

        self.ctx.fail_typecheck(f"Invalid filter value {value}")

    def read_filter_value(self):
        filter_value = self.get_key("filter")

        self.result["filter"] = self.add_path("filter").parse_filter_value(filter_value)


class CachesReader(PropertyReader):
    def __init__(self, ctx: "ConfigContext") -> None:
        super().__init__(ctx)

    @property
    def klass(self):
        return CachesReader

    def read_caches(self) -> config.Caches | None:

        result = {}
        caches = self

        for cache_id in caches.keys():
            result[cache_id] = caches.enter(cache_id).read_cache()

        return config.Caches(result)

    def read_cache(self):
        typ = self.string("type")
        capacity = self.getter("capacity", get_bytes_count)
        block_size = self.getter(
            "block_size", get_bytes_count, default=256 * 1024, optional=True
        )

        return config.Cache(
            typ, kwargs={"capacity": capacity, "block_size": block_size}
        )


class ConfigRootReader(PropertyReader):
    DIR_PROPS_KEYS = {"source", "filter", "cache", "wrappers", "producer", "treat_as"}

    @staticmethod
    def from_mapping(mapping: Mapping):
        return ConfigRootReader(ConfigContext(mapping))

    @property
    def klass(self):
        return ConfigRootReader

    def __init__(self, ctx: "ConfigContext") -> None:
        super().__init__(ctx)

    @property
    def other_keys(self):
        return set(self.ctx.mapping.keys()).difference(self.DIR_PROPS_KEYS)

    @staticmethod
    def parse_filter_value(filter_value: FilterConfigValue) -> list[tuple[str, Any]]:
        return FilterPropReader(ConfigContext({})).parse_filter_value(filter_value)

    def read_source_prop(self):
        source_prop = None
        dir_cfg_reader = self.ctx.get_reader()
        (source_value, t) = dir_cfg_reader.value_with_type("source", optional=True)
        if t == "string":
            source_prop = config.PropSource(source_value)
        elif t == "mapping":
            source_reader = dir_cfg_reader.enter("source")
            source_reader.string("source")
            source_reader.boolean("recursive", optional=True)
            source_reader.assert_no_other_keys(
                f"Unexpected keys in `source` property: {source_reader.other_keys()}",
            )
            source_prop = config.PropSource(**source_reader.get())
        elif t == "none":
            pass
        else:
            dir_cfg_reader.ctx.fail_typecheck(f"Invalid `source` value: {t}")

        return source_prop

    def read_filter_prop(self):
        """
        filter: FILTER_VALUE
        filter: {filter: FILTER_VALUE, recursive}
        FILTER_VALUE = FILTER_VALUE_ITEM | list[FILTER_VALUE_ITEM]
        FILTER_VALUE_ITEM = str | FILTER_VALUE | Mapping[filter_id, FILTER_ARG]
        """
        filter_prop = None
        dir_cfg_reader = self.ctx.get_reader(FilterPropReader)
        (filter_prop_value, t) = dir_cfg_reader.value_with_type("filter", optional=True)

        if t == "string":
            # filter: MessageWithMusic
            filter_prop = config.PropFilter([(filter_prop_value, None)])
        elif t == "list":
            # filter:
            #   - MessageWithMusic
            #   - MessageForwarded
            filter_prop = config.PropFilter(
                dir_cfg_reader.add_path("filter").parse_filter_value(filter_prop_value),
            )
        elif t == "mapping":
            # filter { filter: MessageWithMusic, recursive: True, overwright: False}
            if "filter" in filter_prop_value:
                filter_reader = dir_cfg_reader.enter("filter")
                filter_reader.boolean("overwright", optional=True, default=False)
                filter_reader.boolean("recursive", optional=True, default=False)
                filter_reader.read_filter_value()

                filter_reader.assert_no_other_keys(
                    f"Unexpected keys in `filter` property: {filter_reader.other_keys()}",
                )

                filter_prop = config.PropFilter(**filter_reader.get())
            else:
                filter_prop = config.PropFilter(
                    dir_cfg_reader.parse_filter_value(filter_prop_value),
                )
        elif t == "none":
            pass
        else:
            dir_cfg_reader.ctx.fail(f"Invalid filter value: {filter_prop_value}")

        return filter_prop

    def read_cache_prop(self):
        cache_prop = None
        (cache_prop_value, t) = self.value_with_type("cache", optional=True)

        if t == "string":
            cache_prop = config.PropCacheReference(cache_prop_value)
        elif t == "mapping":
            cache_prop = self.ctx.enter("cache").get_reader(CachesReader).read_cache()
        elif t == "none":
            return
        else:
            self.ctx.fail(f"Invalid cache value: {cache_prop_value}")

        return cache_prop

    def read_producer_prop(self):
        producer_prop = None
        (producer_prop_value, t) = self.value_with_type("producer", optional=True)

        if t == "string":
            producer_prop = config.PropProducer(producer_prop_value)
        elif t == "mapping":
            self.ctx.assert_that(
                len(producer_prop_value) == 1,
                "`producer` has to be a mapping with a single key or a string.",
            )
            producer_name, producer_arg = get_first_pair(producer_prop_value)
            return config.PropProducer(producer_name, producer_arg)
        elif t == "none":
            return
        else:
            self.ctx.fail(f"Invalid `producer` value: {producer_prop_value}")

        return producer_prop

    def read_treat_as_prop(self):
        return map_none(
            self.add_path("treat_as").string_or_list_of_strings("treat_as", True),
            ensure_list,
        )

    def read_wrappers_prop(self):
        wrapper_prop = None
        wrapper_prop_value, t = self.value_with_type("wrappers", True)

        if t == "string":
            wrapper_prop = config.PropWrapper(wrapper_prop_value)
        elif t == "mapping":
            self.ctx.assert_that(
                len(wrapper_prop_value) == 1, f"Wrapper is illegal mapping."
            )
            w_name, w_arg = get_first_pair(wrapper_prop_value)
            wrapper_prop = config.PropWrapper(w_name, w_arg)
        elif t == "none":
            pass
        else:
            self.ctx.fail(f"Invalid wrapper value: {wrapper_prop_value}")

        return wrapper_prop

    def read_root(self):

        source_prop = self.read_source_prop()
        filter_prop = self.read_filter_prop()
        cache_prop = self.read_cache_prop()
        producer_prop = self.read_producer_prop()
        treat_as_prop = self.read_treat_as_prop()
        wrapper_prop = self.read_wrappers_prop()

        other_keys = {}

        for other_key in self.other_keys:
            other_key_root = (
                self.ctx.enter(other_key).get_reader(ConfigRootReader).read_root()
            )
            other_keys[other_key] = other_key_root

        return config.DirConfig(
            source=source_prop,
            filter=filter_prop,
            cache=cache_prop,
            producer=producer_prop,
            treat_as=treat_as_prop,
            wrapper=wrapper_prop,
            other_keys=other_keys,
        )


class ConfigReader(CachesReader, ConfigRootReader):
    @staticmethod
    def from_mapping(mapping: Mapping):
        return ConfigReader(ConfigContext(mapping))

    @property
    def klass(self):
        return ConfigReader

    def __init__(self, ctx: "ConfigContext") -> None:
        super().__init__(ctx)

    def read_client(self) -> config.Client:
        self.string("session")
        self.integer("api_id")
        self.string("api_hash")
        self.getter("request_size", get_bytes_count)
        return config.Client(**self.get())

    def read_message_sources(self):
        result = {}
        for source_id in self.keys():
            source_reader = self.enter(source_id)
            result[source_id] = source_reader.read_message_source()

        return config.MessageSources(result)

    def read_message_source(self):
        return self.ctx.failing(
            lambda: config.MessageSource.from_mapping(self.ctx.mapping),
        )

    def read_config(self) -> config.Config:

        mount_dir = self.string("mount_dir", True)
        client = self.enter("client").read_client()

        message_sources = self.enter("message_sources").read_message_sources()

        if self.has("caches"):
            caches = self.enter("caches").read_caches()
        else:
            caches = None

        root = self.enter("root").read_root()

        return config.Config(
            mount_dir=mount_dir,
            client=client,
            message_sources=message_sources,
            caches=caches,
            root=root,
        )


from . import types


class ConfigParser(ConfigParserProto, ConfigParserFilter):
    def parse_root(self, mapping: Mapping) -> types.DirConfig:
        return ConfigReader(ConfigContext(mapping)).read_root()

    def parse_config(self, mapping: Mapping) -> types.Config:
        return ConfigReader(ConfigContext(mapping)).read_config()

    def parse_filter_value(
        self, filter_value: types.FilterConfigValue
    ) -> types.FilterInputType:
        return ConfigReader(ConfigContext({})).parse_filter_value(filter_value)
