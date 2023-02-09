import pytest
import yaml

from tgmount.config import *
from tgmount.config.config import ConfigReader, DirConfigReader
from tgmount.tgmount.extensions.writable import (
    TgmountExtensionWritable,
    WritableDirConfig,
)


def test_reader1():
    reader = ConfigReader.from_mapping(
        {
            "client": {
                "session": "123",
                "api_id": 123,
                "api_hash": "1234",
            },
            "message_sources": {},
            "root": {
                "source": "source1",
                "upload": True,
                "folder2": {
                    "source": "source1",
                    "upload": False,
                },
            },
        },
        extensions={
            DirConfigReader: [TgmountExtensionWritable()],
        },
    )

    cfg = reader.read_config()

    assert (
        cfg.root.extra.get(
            TgmountExtensionWritable.prop,
            WritableDirConfig,
        ).upload
        == True
    )
    assert (
        cfg.root.other_keys["folder2"]
        .extra.get(TgmountExtensionWritable.prop, WritableDirConfig)
        .upload
        == False
    )
