from typing import TypeVar, Mapping, Optional, Any, TypedDict

from tgmount import config
from tgmount.config.helpers import assert_that
from tgmount.config.error import ConfigErrorWithPath
from tgmount.util import col, dict_exclude, yes
from .filters_types import FilterConfigValue, Filter
from .root_config_types import RootConfigWalkingContext
from .tgmount_types import TgmountResources
from .types import TgmountRootType

T = TypeVar("T")

from .logger import module_logger


class RootConfigError(ConfigErrorWithPath):
    pass


class PropertyValidator:
    def __init__(self, path: list[str]) -> None:
        self.path = path


class _RootConfigReaderProps:
    DIR_PROPS_KEYS = {"source", "filter", "cache", "wrappers", "producer", "treat_as"}

    PropSourceType = TypedDict("PropSource", source_name=str, recursive=bool)
    PropFilterType = TypedDict(
        "PropFilter",
        filters=list[tuple[str, Mapping | None]],
        recursive=bool,
        overwright=bool,
    )

    logger = module_logger.getChild(f"RootProducerPropsReader")

    @classmethod
    def read_prop_source(cls, d: TgmountRootType) -> PropSourceType | None:
        source_prop_cfg: Mapping | str | None = d.get("source")

        if source_prop_cfg is None:
            return

        if isinstance(source_prop_cfg, str):
            source_name = source_prop_cfg
            recursive = False
        else:
            source_name: str | None = source_prop_cfg.get("source")
            assert isinstance(source_name, str), f"Invalid source name: {source_name}"
            recursive = source_prop_cfg.get("recursive", False)
            assert isinstance(
                recursive, bool
            ), f"Invalid value for recursive: {recursive}"

        return cls.PropSourceType(source_name=source_name, recursive=recursive)

    def read_prop_filter(self, d: TgmountRootType) -> PropFilterType | None:
        filter_prop_cfg = d.get("filter")

        if filter_prop_cfg is None:
            return

        filter_prop_cfg

        filter_recursive = False
        filter_overwright = False

        if isinstance(filter_prop_cfg, Mapping) and "filter" in filter_prop_cfg:
            filter_recursive = filter_prop_cfg.get("recursive", False)
            filter_overwright = filter_prop_cfg.get("overwright", False)
            filter_prop_cfg = filter_prop_cfg["filter"]

        if not isinstance(filter_prop_cfg, list):
            filter_prop_cfg = [filter_prop_cfg]

        filter_prop_cfg = to_list_of_single_key_dicts(filter_prop_cfg)  # type: ignore

        filters: list[tuple[str, Mapping | None]] = []

        for f_item in filter_prop_cfg:
            if isinstance(f_item, str):
                f_name = f_item
                filter_arg = None
            else:
                f_name, filter_arg = col.get_first_pair(f_item)

            filters.append((f_name, filter_arg))

        return self.PropFilterType(
            filters=filters,
            recursive=filter_recursive,
            overwright=filter_overwright,
        )

    def read_prop_cache(self, d: TgmountRootType) -> str | Mapping | None:
        _cache = d.get("cache")

        if _cache is None:
            return

        if isinstance(_cache, str):
            return _cache

        elif isinstance(_cache, Mapping):
            cache_type = _cache.get("type")

            if cache_type is None:
                raise config.ConfigError(
                    f"Invalid cache value: {_cache}. Missing type."
                )

            cache_kwargs = dict_exclude(_cache, ["type"])

            return {"type": cache_type, "kwargs": cache_kwargs}

        raise config.ConfigError(
            f"Invalid cache value: {_cache}. Expected mapping or string."
        )

    def read_prop_wrappers(
        self, d: TgmountRootType
    ) -> Optional[list[tuple[str, Any | None]]]:
        _wrappers = d.get("wrappers")

        if _wrappers is None:
            return

        if not isinstance(_wrappers, list):
            _wrappers = [_wrappers]

        wrappers = []

        for w_item in _wrappers:
            if isinstance(w_item, str):
                wrapper_name = w_item
                wrapper_arg = None
            else:
                wrapper_name, wrapper_arg = col.get_first_pair(w_item)

            wrappers.append((wrapper_name, wrapper_arg))

        return wrappers

    def read_prop_treat_as(self, d: TgmountRootType) -> list[str] | None:
        value = d.get("treat_as")

        if value is None:
            return

        if isinstance(value, str):
            return [value]
        elif isinstance(value, list):
            return value

        raise config.ConfigError(f"Invalid treat_as value: {value}")

    def read_prop_factory(self, d: TgmountRootType) -> Mapping[str, Any] | None:
        factory_cfg = d.get("factory")

        if not yes(factory_cfg):
            return

        if not isinstance(factory_cfg, dict):
            raise config.ConfigError(f"Invalid 'factory' value: {factory_cfg}")

        opt_recursive = factory_cfg.get("recursive", False)
        opt_mount_texts = factory_cfg.get("mount_texts", False)
        opt_treat_as = factory_cfg.get("treat_as", [])

        if isinstance(opt_treat_as, str):
            opt_treat_as = [opt_treat_as]
        elif isinstance(opt_treat_as, list):
            for v in opt_treat_as:
                if not isinstance(v, str):
                    raise config.ConfigError(
                        f"Invalid 'factory.treat_as' value: {opt_treat_as}"
                    )
        else:
            raise config.ConfigError(
                f"Invalid 'factory.treat_as' value: {opt_treat_as}"
            )

        return dict(
            recursive=opt_recursive,
            mount_texts=opt_mount_texts,
            treat_as=opt_treat_as,
        )

    def read_prop_producer(self, d: TgmountRootType) -> tuple[str, Any] | None:
        _producer_dict = d.get("producer")

        if _producer_dict is None:
            return

        if isinstance(_producer_dict, str):
            _producer_dict = {_producer_dict: {}}

        producer_name = col.get_first_key(_producer_dict)

        if producer_name is None:
            raise config.ConfigError(f"Invalid producer definition: {_producer_dict}")

        producer_arg = _producer_dict[producer_name]

        return producer_name, producer_arg

    def get_filters_from_prop(
        self,
        filter_prop: list,
        resources: TgmountResources,
        ctx: RootConfigWalkingContext,
    ) -> list[Filter]:
        def _parse_filter(filt: FilterConfigValue) -> list[Filter]:
            self.logger.info(f"filt={filt}")

            filter_prop = self.read_prop_filter({"filter": filt})

            if filter_prop is None:
                return []

            return self.get_filters_from_prop(filter_prop["filters"], resources, ctx)

        filters = []

        for f_name, f_arg in filter_prop:
            self.logger.info(f"{f_name} {f_arg}")

            filter_cls = resources.filters_provider.get(f_name)

            if filter_cls is None:
                raise config.ConfigError(
                    f"Missing filter: {f_name} in {ctx.current_path}"
                )

            _filter = filter_cls.from_config(f_arg, ctx, _parse_filter)

            filters.append(_filter)

        return filters


def to_list_of_single_key_dicts(
    items: list[str | Mapping[str, dict]]
) -> list[str | Mapping[str, dict]]:
    res = []

    for item in items:
        if isinstance(item, str):
            res.append(item)
        else:
            res.extend(dict([t]) for t in item.items())

    return res
