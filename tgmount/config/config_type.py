from abc import abstractmethod
from typing import Any, Mapping, Protocol
from . import types


class ConfigParserFilter(Protocol):
    @abstractmethod
    def parse_filter_value(
        self, filter_value: types.FilterConfigValue
    ) -> types.FilterInputType:
        ...


class ConfigRootParserProto(Protocol):
    @abstractmethod
    def parse_root(self, mapping: Mapping) -> types.DirConfig:
        ...


class ConfigParserProto(ConfigRootParserProto, Protocol):
    @abstractmethod
    def parse_config(self, mapping: Mapping) -> types.Config:
        ...
