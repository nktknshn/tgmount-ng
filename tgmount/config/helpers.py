import typing
from typing import Any, Callable, Mapping
from dataclasses import fields, MISSING
from typing import Optional, Type, TypeGuard, TypeVar, Union, overload
from tgmount.config.error import (
    ConfigPropertyError,
    ConfigError,
    MissingKeyError,
    TypecheckError,
)
from tgmount.config.util import get_type_name

from tgmount.util import col, none_fallback
from .logger import logger

T = TypeVar("T")


@overload
def assert_that(condition: TypeGuard[T], error: Exception) -> TypeGuard[T]:
    ...


@overload
def assert_that(condition: bool, error: Exception) -> bool:
    ...


def assert_that(
    condition: bool | TypeGuard[T], error: Exception
) -> TypeGuard[T] | bool:
    if not condition:
        raise error

    return True


def assert_not_none(pred: Optional[T], e) -> TypeGuard[T]:
    if pred is None:
        raise e
    return True


def _typecheck_union(
    value,
    typ,
):

    type_args = typing.get_args(typ)

    if type(value) is list:

        for arg in type_args:
            _type_origin = typing.get_origin(arg)

            if _type_origin is list:
                (_typ,) = typing.get_args(arg)
                for v in value:
                    if type(v) is not _typ:
                        return False

                return True

        return False

    else:
        typechekd = col.contains(type(value), type_args)

    return typechekd


def require(value: Optional[T], e) -> T:
    if value is None:
        raise e

    return value


def dict_get_value(
    d: Mapping,
    key: str,
    typ: Type[T],
    e: Exception,
    default=Optional[T],
) -> T:
    dv = d.get(key, default)
    dv = type_check(T, typ, e)

    return dv


def type_check(value: Any, typ: Type[T], error: Exception) -> T:
    if typ == Mapping:
        if isinstance(value, Mapping):
            return value
        raise error
    # print(value, typ)
    type_origin = typing.get_origin(typ)
    type_args = typing.get_args(typ)

    if type_origin is Optional:
        if value is None:
            return None
        typechekd = typ is Optional[type(value)]
    elif type_origin is Union:
        typechekd = _typecheck_union(value, typ)
    else:
        typechekd = typ is type(value)

    if not typechekd:
        raise error

    return value


Loader = Callable[[Mapping], T]


class ConfigDataclassError(ConfigError):
    def __init__(
        self, typ: Type, kwargs: Mapping, error: Exception, message: str | None = None
    ) -> None:
        super().__init__(
            none_fallback(message, f"Error constructing type {typ}. kwargs: {kwargs}")
        )
        self.typ = typ
        self.kwargs = kwargs
        self.error = error


def load_class_from_mapping(
    cls,
    mapping: Mapping,
    *,
    loaders: Optional[Mapping[str, Loader]] = None,
    ignore_unexpected_key=False,
):
    logger.debug(f"load_class_from_dict({cls}, {mapping}, {loaders})")

    loaders = loaders if loaders is not None else {}

    assert_that(
        isinstance(mapping, Mapping),
        ConfigError(f"{mapping} is not a mapping"),
    )

    dataclass_kwargs = {}

    other_keys = set(mapping.keys()).difference(set(f.name for f in fields(cls)))

    if len(other_keys) > 0 and not ignore_unexpected_key:
        raise ConfigError(f"Unexpected keys: {other_keys}")

    for field in fields(cls):
        if (loader := loaders.get(field.name)) is not None:
            try:
                dataclass_kwargs[field.name] = loader(mapping)
                continue
            except Exception as e:
                raise ConfigPropertyError(field.name, e)

        value = mapping.get(field.name, field.default)

        if value is MISSING:
            raise ConfigPropertyError(
                field.name,
                MissingKeyError(field.name),
                f"Missing required property `{field.name}: {get_type_name(field.type)}`",
            )

        type_check(
            value,
            field.type,
            ConfigPropertyError(
                field.name,
                TypecheckError(
                    expected_type=field.type,
                    actual_type=type(value),
                ),
            ),
        )

        dataclass_kwargs[field.name] = value

    try:
        return cls(**dataclass_kwargs)
    except TypeError as e:
        raise ConfigDataclassError(cls, dataclass_kwargs, e)


def load_mapping(cls: Type | Callable, d: Mapping):
    def load_class(d):
        if hasattr(cls, "from_mapping"):
            return cls.from_mapping(d)

        if isinstance(cls, Type):
            return load_class_from_mapping(cls, d)

        return cls(d)

    return {k: load_class(v) for k, v in d.items()}


T = TypeVar("T")
R = TypeVar("R")

# Tree = T | Mapping[str, "Tree[T]"]


# def fold_tree(
#     f: Callable[[T, R], R],
#     tree: Tree[T],
#     initial: R,
# ) -> R:
#     res = initial
#     if isinstance(tree, Mapping):
#         for k, v in tree.items():
#             if isinstance(v, Mapping):
#                 res = fold_tree(f, v, res)
#             else:
#                 res = f(v, res)
#     else:
#         return f(tree, res)

#     return res
