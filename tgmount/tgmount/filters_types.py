from abc import abstractmethod
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, TypeVar

from tgmount.common.filter import FilterAllMessagesProto
from tgmount.config.config import FilterConfigValue
from tgmount.tgclient.message_types import MessageProto
from tgmount.tgmount.file_factory import ClassifierBase, FileFactoryBase
from tgmount.tgmount.file_factory.types import FileFactoryProto

T = TypeVar("T")
FilterAllMessages = FilterAllMessagesProto
FilterSingleMessage = Callable[[MessageProto], T | None | bool]
Filter = FilterAllMessages
FilterParser = Callable[[FilterConfigValue], list[Filter]]


class FilterContext(Protocol):
    file_factory: FileFactoryProto
    classifier: ClassifierBase


class FilterFromConfigProto:
    @staticmethod
    @abstractmethod
    def from_config(
        filter_arg: Any, ctx: FilterContext, parse_filter: FilterParser
    ) -> Optional["FilterAllMessagesProto"]:
        ...
