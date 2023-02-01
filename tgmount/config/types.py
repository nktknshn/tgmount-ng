from dataclasses import dataclass, field, replace
import datetime
from typing import Any, Mapping, Optional, Union
import yaml
from tgmount import vfs
from tgmount.config.helpers import load_class_from_mapping

from tgmount.util import get_bytes_count, map_none, col

import time


DATE_FORMATS = [
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%d/%m/%y",
]

FilterConfigValue = str | dict[str, Mapping] | list[str | dict[str, Mapping]]
FilterInputType = list[tuple[str, Any]]


def parse_datetime(s: str):
    error = ValueError(f"Invalid value: {s}. Date formats are: {DATE_FORMATS}")

    if not isinstance(s, str):
        raise error

    for f in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, f)
        except ValueError:
            continue

    raise error


@dataclass
class Cache:
    type: str
    kwargs: Mapping

    @staticmethod
    def from_mapping(mapping: Mapping) -> "Cache":
        return load_class_from_mapping(
            Cache,
            mapping,
            loaders={"kwargs": lambda d: col.dict_exclude(d, ["type"])},
            ignore_unexpected_key=True,
        )


@dataclass
class Caches:
    caches: dict[str, Cache]


@dataclass
class Wrapper:
    type: str
    kwargs: dict

    @staticmethod
    def from_mapping(d: dict) -> "Wrapper":
        return load_class_from_mapping(
            Wrapper,
            d,
            loaders={"kwargs": lambda d: col.dict_exclude(d, ["type"])},
            ignore_unexpected_key=True,
        )


@dataclass
class Wrappers:
    wrappers: dict[str, Wrapper]


@dataclass
class Client:
    session: str
    api_id: int
    api_hash: str
    request_size: int | None = None

    @staticmethod
    def from_mapping(mapping: Mapping) -> "Client":
        return load_class_from_mapping(
            Client,
            mapping,
            loaders={
                "request_size": lambda d: map_none(
                    d.get("request_size"), get_bytes_count
                )
            },
        )


@dataclass
class MessageSource:
    entity: Union[str, int]
    filter: Optional[str] = None
    limit: Optional[int] = None
    offset_id: int = 0
    min_id: int = 0
    max_id: int = 0
    wait_time: Optional[float] = None
    reply_to: Optional[int] = None
    from_user: Optional[str | int] = None
    reverse: bool = False
    updates: Optional[bool] = None
    offset_date: Optional[datetime.datetime] = None

    @staticmethod
    def from_mapping(mapping: Mapping) -> "MessageSource":
        return load_class_from_mapping(
            MessageSource,
            mapping,
            loaders={
                "offset_date": lambda d: map_none(
                    d.get("offset_date"),
                    parse_datetime,
                )
            },
        )


@dataclass
class MessageSources:
    sources: dict[str, MessageSource]


@dataclass
class PropSource:
    source: str
    recursive: bool = False


@dataclass
class PropFilter:
    filter: list[tuple[str, Any | None]]
    recursive: bool = False
    overwright: bool = False


@dataclass
class PropProducer:
    producer: str
    kwargs: Any = None


@dataclass
class PropWrapper:
    wrapper: str
    kwargs: Mapping | None = None

    @staticmethod
    def from_mapping(mapping: Mapping):
        return load_class_from_mapping(
            PropWrapper,
            mapping,
            loaders={"kwargs": lambda d: col.dict_exclude(d, ["type"])},
            ignore_unexpected_key=True,
        )


@dataclass
class PropCacheReference:
    cache: str


PropCache = PropCacheReference | Cache


@dataclass
class DirConfig:
    source: PropSource | None = None
    filter: PropFilter | None = None
    producer: PropProducer | None = None
    wrapper: PropWrapper | None = None
    cache: PropCache | None = None
    treat_as: list[str] | None = None
    other_keys: Mapping[str, "DirConfig"] = field(default_factory=dict)


@dataclass
class Config:
    client: Client
    message_sources: MessageSources
    root: DirConfig
    caches: Optional[Caches] = None
    wrappers: Optional[Wrappers] = None
    mount_dir: Optional[str] = None

    def set_root(self, root_cfg: DirConfig) -> "Config":
        return replace(self, root=root_cfg)
