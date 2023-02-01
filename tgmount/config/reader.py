from typing import Any, Callable, Literal, Type, TypeVar, overload
from typing_extensions import Self
from tgmount import config
from tgmount.config.error import (
    ConfigError,
    ConfigErrorWithPath,
    MissingKeyError,
    TypecheckError,
)
from tgmount.util import get_bytes_count, map_none, no
from tgmount.util.col import get_first_pair


from .logger import logger
from collections.abc import Mapping

T = TypeVar("T")


ValueType = (
    Literal["string"]
    | Literal["integer"]
    | Literal["mapping"]
    | Literal["list"]
    | Literal["none"]
    | Literal["boolean"]
)


def ensure_list(value: T | list[T]) -> list[T]:
    if isinstance(value, list):
        return value

    return [value]


class PropertyReader:
    logger = logger.getChild("PropertyReader")

    def __init__(self, ctx: "ConfigContext") -> None:
        self.result = {}
        self.ctx = ctx
        self._keys_read: set[str] = set()

    def get(self) -> Mapping:
        return self.result

    def has(self, key: str):
        return key in self.ctx.mapping

    def get_key(self, key: str, optional=False, default=None) -> Any | None:
        self._keys_read.add(key)
        value = self.ctx.mapping.get(key, default)
        if not optional and value is None:
            self.ctx.fail(MissingKeyError(key))
        return value

    def _get_key(self, key, typ, optional, default):
        value = self.get_key(key, optional, default)
        if optional and value is None:
            return
        self.ctx.assert_type(
            value,
            typ,
            f"Property `{key}` has invalid value: `{value}`. Expected type {typ}",
        )
        self.result[key] = value
        return value

    def integer(
        self, key: str, *, optional: bool = False, default: int | None = None
    ) -> int | None:
        return self._get_key(key, int, optional, default)

    @overload
    def string(self, key: str) -> str:
        ...

    @overload
    def string(self, key: str, optional: Literal[True]) -> str | None:
        ...

    def string(
        self, key: str, optional: bool = False, default: str | None = None
    ) -> str | None:
        return self._get_key(key, str, optional, default)

    def boolean(
        self, key: str, optional: bool = False, default: bool | None = None
    ) -> bool | None:
        return self._get_key(key, bool, optional, default)

    def string_or_int(
        self, key: str, optional: bool = False, default: str | int | None = None
    ) -> str | int | None:
        value = self.get_key(key, optional, default)

        if isinstance(value, str):
            self.result[key] = value
            return value

        if isinstance(value, int):
            self.result[key] = value
            return value

        if optional and no(value):
            return

        self.ctx.fail_typecheck(f"Invalid value: {value}")

    def string_or_list_of_strings(
        self, key: str, optional: bool = False, default: str | int | None = None
    ) -> str | list[str] | None:
        value = self.get_key(key, optional, default)

        if isinstance(value, str):
            self.result[key] = value
            return value

        if isinstance(value, list):
            for idx, el in enumerate(value):
                self.add_path(str(idx)).ctx.assert_type(
                    el, str, f"Expected string, received: {type(el)}"
                )
            self.result[key] = value
            return value

        if optional and no(value):
            return

        self.ctx.fail_typecheck(f"Invalid value: {value}")

    def string_or_mapping(
        self, key: str, optional: bool = False, default: str | int | None = None
    ) -> str | Mapping | None:
        value = self.get_key(key, optional, default)

        if isinstance(value, str):
            self.result[key] = value
            return value

        if isinstance(value, Mapping):
            self.result[key] = value
            return value

        self.ctx.fail_typecheck(f"Invalid value: {value}")

    def getter(
        self,
        key: str,
        getter: Callable[[Any], T],
        optional: bool = False,
        default: T = None,
    ) -> T | None:
        try:
            value = self.get_key(key, optional)
            if value is None:
                return default
            self.result[key] = getter(value)
            return self.result[key]
        except ConfigErrorWithPath as e:
            raise e
        except Exception as e:
            self.ctx.fail(e)

    def typeof_value(self, value: Any) -> ValueType:
        if isinstance(value, list):
            return "list"

        if isinstance(value, str):
            return "string"
        if isinstance(value, (Mapping, dict)):
            return "mapping"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, bool):
            return "boolean"
        if value is None:
            return "none"

        self.ctx.fail(f"Unsupported type: {value}")

    def typeof(self, key: str) -> ValueType:
        return self.typeof_value(self.get_key(key))

    def value_with_type(self, key: str, optional=False) -> tuple[Any, ValueType]:
        value = self.get_key(key, optional=optional)

        return value, self.typeof_value(value)

    def read(self, props: Mapping[str, Type]):
        pass

    def add_path(self, key: str) -> Self:
        return self.klass(ConfigContext(self.ctx.mapping, [*self.ctx.path, key]))

    def enter(self, key: str) -> Self:
        self.logger.debug(f"enter({key})")
        return self.ctx.enter(key).get_reader(self.klass)

    @property
    def klass(self):
        return PropertyReader

    def keys(self) -> list[str]:
        return list(self.ctx.mapping.keys())

    def other_keys(self):
        return set(self.ctx.mapping.keys()).difference(self._keys_read)

    def assert_no_other_keys(self, error: "InputErrorType"):
        self.ctx.assert_that(len(self.other_keys()) == 0, error)


InputErrorType = str | ConfigError | Exception

R = TypeVar("R", bound=PropertyReader)


class ConfigContext:
    logger = logger.getChild(f"ConfigContext")

    def __init__(self, mapping: Mapping, path: list[str] = []):
        self.mapping = mapping
        self.path = path

    def get_property(self, key: str, typ: Type[T]):
        pass

    def keys(self) -> list[str]:
        return list(self.mapping.keys())

    def failing(self, lazy_value: Callable[[], T]) -> T:
        try:
            return lazy_value()
        except Exception as e:
            self.fail(e)

    def enter(self, key: str) -> "ConfigContext":
        self.logger.debug(f"enter({key}")
        mapping = self.mapping.get(key)

        if mapping is None:
            self.fail(f"Missing key: {key}")

        self.assert_type(mapping, dict, f"Cannot enter key `{key}`. Expected mapping.")

        return ConfigContext(mapping, path=[*self.path, key])

    def fail(self, error: InputErrorType):
        raise ConfigErrorWithPath(self.path, self.get_error(error), str(error))

    def fail_typecheck(self, error: str):
        raise ConfigErrorWithPath(self.path, TypecheckError(None, None, error))

    def get_error(self, e: InputErrorType):
        if isinstance(e, str):
            return ConfigError(e)

        return e

    def assert_type(
        self, value: Any, typ: Type, error: InputErrorType | None = None
    ) -> Any:
        if isinstance(value, typ):
            return value

        # ConfigError()
        self.fail(
            TypecheckError(typ, type(value), map_none(error, self.get_error)),
        )

    def assert_that(self, condition, error):
        if not condition:
            self.fail(self.get_error(error))

    def get_reader(self, klass: Type[R] = PropertyReader) -> R:
        return klass(self)
