from abc import abstractmethod
from typing import Mapping, Optional, Protocol, Type, Callable
from tgmount.common.filter import FilterAllMessagesProto

from tgmount.config import ConfigError
from tgmount.tgclient.message_source import MessageSourceFilter
from tgmount.tgclient.message_types import MessageProto
from tgmount.util import none_fallback
from ..filters_types import (
    FilterContext,
    FilterFromConfigProto,
    Filter,
    FilterParser,
)

"""Taking a string, return `FilterFromConfigProto` class"""
FilterGetter = Callable[[str], Type[FilterFromConfigProto]]


class FilterProviderProto(Protocol):

    telegram_filters: Mapping[str, Type[FilterAllMessagesProto[MessageProto]]]

    @abstractmethod
    def get(self, filter_name: str) -> Type[FilterFromConfigProto] | None:
        pass


class FilterProviderBase(FilterProviderProto):
    """ """

    filters: Mapping[str, Type[Filter]]
    filter_getters: list[FilterGetter]

    telegram_filters: Mapping[str, Type[MessageSourceFilter[MessageProto]]]

    def __init__(
        self,
    ) -> None:
        pass
        # super().__init__()

    def append_filter_getter(self, fgetter: FilterGetter):
        self.filter_getters.append(fgetter)

    def get(self, key) -> Optional[Type[FilterFromConfigProto]]:
        _filter = self.filters.get(key)

        if _filter is not None:
            return _filter  # type: ignore

        if len(self.filter_getters) == 0:
            return

        _fgs: list[Type[FilterFromConfigProto]] = []

        for filter_getter in self.filter_getters:
            _fgs.append(filter_getter(key))

        class _FromConfig(FilterFromConfigProto):
            @staticmethod
            def from_config(d, ctx: FilterContext, parse_filter: FilterParser):
                for fg in _fgs:
                    if _f := fg.from_config(d, ctx, parse_filter):
                        return _f
                raise ConfigError(f"Invalid filter: {key}")

        return _FromConfig
