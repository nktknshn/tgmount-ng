from typing import Mapping
from tgmount import config
from tgmount.config.config import ConfigParser, Extensions
from tgmount.config.config_type import ConfigRootParserProto
from tgmount.main.util import read_tgapp_api

DEFAULT_CACHES: Mapping = {
    "memory1": {
        "type": "memory",
        "kwargs": {"capacity": "50MB", "block_size": "128KB"},
    }
}


DEFAULT_ROOT: Mapping = {
    "source1": {
        "source": {"source": "source1", "recursive": True},
        # "all": {"filter": "All"},
        # "wrappers": "ExcludeEmptyDirs",
        # "texts": {"filter": "MessageWithText"},
    },
}


def create_config(
    *,
    message_sources={"source1": "source1"},
    caches=DEFAULT_CACHES,
    root: Mapping = DEFAULT_ROOT,
    config_reader: ConfigRootParserProto = ConfigParser(),
    extensions: Extensions
) -> config.Config:
    api_id, api_hash = read_tgapp_api()

    _message_sources = {
        k: config.MessageSource(entity=v) for k, v in message_sources.items()
    }

    _caches = {
        k: config.Cache(type=v["type"], kwargs=v["kwargs"]) for k, v in caches.items()
    }

    return config.Config(
        client=config.Client(api_id=api_id, api_hash=api_hash, session="tgfs"),
        message_sources=config.MessageSources(sources=_message_sources),
        caches=config.Caches(_caches),
        root=config_reader.parse_root(root, extensions),
    )
