from types import NoneType
from typing import Any, ClassVar, Mapping, Protocol, Type, TypeVar, cast, overload
from tgmount.error import TgmountError
from tgmount.util import nn

T = TypeVar("T")


class ExtraError(TgmountError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class Namespace:
    def __init__(self) -> None:
        self._attributes: dict[str, Any] = {}

    def __getattribute__(self, __name: str) -> Any:
        try:
            return super(Namespace, self).__getattribute__(__name)
        except AttributeError:
            pass

        return self._attributes[__name]

    def __setattr__(self, __name: str, __value: Any) -> None:
        try:
            return super(Namespace, self).__setattr__(__name, __value)
        except AttributeError:
            pass

        self._attributes[__name] = __value


class ExtraProto(Protocol):
    extra_name: ClassVar[str]


E = TypeVar("E", bound=ExtraProto)


class Extra:
    def __init__(self) -> None:
        self._extra: dict[str, Namespace] = {}

    def __repr__(self) -> str:
        if len(self._extra.keys()):
            return f"Extra({list(self._extra.keys())})"
        return "empty"

    def __getattribute__(self, __name: str) -> Namespace:
        try:
            return super(Extra, self).__getattribute__(__name)
        except AttributeError:
            pass

        extra = self._extra.get(__name)

        if extra is None:
            raise ExtraError(f"Missing extra named {__name}")

        return extra

    @overload
    def get(self, name: Type[E], typ: NoneType = None) -> E:
        ...

    @overload
    def get(self, name: str, typ: Type[T]) -> T:
        ...

    def get(self, name, typ=None) -> T | E | None:
        v = self.try_get(name, typ)

        if v is None:
            raise TgmountError(f"Missing extra {name}")

        return v

    @overload
    def try_get(self, name: Type[E], typ: NoneType = None) -> E | None:
        ...

    @overload
    def try_get(self, name: str, typ: Type[T]) -> T | None:
        ...

    def try_get(self, name, typ=None):
        # if hasattr(name, "extra_name"):
        if isinstance(name, str):
            try:
                return cast(T, getattr(self, name))
            except AttributeError:
                return None

        return self.try_get(name.extra_name, name)

    def get_or_create(self, name: str, typ: Type[T]) -> T:
        try:
            return cast(T, getattr(self, name))
        except AttributeError:
            return self.create(name, typ)

    def put(self, name: str, extra: Namespace):
        self._extra[name] = extra

    def has(self, name: str) -> bool:
        return bool(self.try_get(name, Any))

    def create(
        self,
        name: str,
        type: Type[T] = Namespace,
        content: Mapping[str, Any] | None = None,
    ) -> T:
        self._extra[name] = Namespace()

        if nn(content):
            for k, v in content.items():
                setattr(self._extra[name], k, v)

        return cast(T, self._extra[name])
