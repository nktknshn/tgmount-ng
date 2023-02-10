from abc import abstractmethod
from typing import Any, Awaitable, Callable, Generic, Iterable, Protocol, TypeVar
from typing_extensions import TypeVarTuple, Unpack

from telethon import events
from tgmount.common.subscribable import SubscribableProto

from tgmount.tgclient.message_types import MessageProto
from tgmount.tgclient.messages_collection import WithId


M = TypeVar("M", bound=WithId)


# class MessageSourceProto(Generic[M], Protocol):
#     @abstractmethod
#     async def get_messages(self) -> list[M]:
#         pass


class MessageSourceProto(Generic[M], Protocol):
    event_new_messages: SubscribableProto[list[M]]
    event_removed_messages: SubscribableProto[list[M]]
    event_edited_messages: SubscribableProto[list[M]]

    @abstractmethod
    async def get_messages(self) -> list[M]:
        ...

    @abstractmethod
    async def set_messages(self, messages: list[M], notify=True):
        pass

    @abstractmethod
    async def add_messages(self, messages: Iterable[M]):
        pass

    @abstractmethod
    async def edit_messages(self, messages: Iterable[M]):
        pass

    @abstractmethod
    async def get_by_ids(self, ids: list[int]) -> list[M] | None:
        pass

    @abstractmethod
    async def remove_messages_ids(self, removed_messages: list[int]):
        pass
