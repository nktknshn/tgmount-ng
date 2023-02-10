from abc import abstractmethod
from typing import Any, Awaitable, Callable, Generic, Protocol, TypeVar

from typing_extensions import TypeVarTuple

Arg = TypeVar("Arg")
T = TypeVar("T")

Ts = TypeVarTuple("Ts")
Arg_co = TypeVar("Arg_co", covariant=True)
Arg2_co = TypeVar("Arg2_co", covariant=True)

Listener = Callable[
    [Any, Arg],
    Awaitable[None],
]


class SubscribableProto(Protocol[Arg_co]):
    @abstractmethod
    def subscribe(self, listener: Listener[Arg_co]):
        ...

    @abstractmethod
    def unsubscribe(self, listener: Listener[Arg_co]):
        ...


class Subscribable(SubscribableProto[Arg]):
    def __init__(self) -> None:
        self._listeners: list[Listener[Arg]] = []

    def subscribe(self, listener: Listener[Arg]):
        self._listeners.append(listener)

    def unsubscribe(self, listener: Listener[Arg]):
        self._listeners.remove(listener)

    async def notify(self, *args):
        for listener in self._listeners:
            await listener(self, *args)


class SubscribableListener(Generic[T]):
    def __init__(self, source: Subscribable, exclusively=False) -> None:
        self.source = source
        self.events: list[T] = []
        self.exclusively = exclusively
        self._subs = []

    async def _append_events(self, sender, events: list[T]):
        self.events.extend(events)

    async def __aenter__(self):
        if not self.exclusively:
            self.source.subscribe(self._append_events)
        else:
            self._subs = self.source._listeners
            self.source._listeners = [self._append_events]

    async def __aexit__(self, type, value, traceback):
        if not self.exclusively:
            self.source.unsubscribe(self._append_events)
        else:
            self.source._listeners = self._subs
