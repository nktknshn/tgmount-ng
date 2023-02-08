from typing import Any, Type, TypeVar, cast
from tgmount.error import TgmountError

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


class Extra:
    def __init__(self) -> None:
        self._extra: dict[str, Namespace] = {}

    def __getattribute__(self, __name: str) -> Namespace:
        try:
            return super(Extra, self).__getattribute__(__name)
        except AttributeError:
            pass

        extra = self._extra.get(__name)

        if extra is None:
            raise ExtraError(f"Missing extra named {__name}")

        return extra

    def get(self, name: str, type: Type[T]) -> T | None:
        try:
            return cast(T, getattr(self, name))
        except AttributeError:
            return None

    def put(self, name: str, extra: Namespace):
        self._extra[name] = extra

    def create(self, name: str, type: Type[T] = Namespace) -> T:
        self._extra[name] = Namespace()
        return cast(T, self._extra[name])
