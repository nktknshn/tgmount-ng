from abc import abstractmethod
import dataclasses
from typing import Any, Protocol
import pytest
import yaml
import os
from pprint import pprint
from tgmount import config
from tgmount.config import *
from tgmount.config.config import ConfigParser, ConfigReader, DirConfigReader
from tgmount.config.reader import TgmountConfigExtensionProto
from tgmount.tgclient.uploader import TelegramFileUploader
from tgmount.tgmount.extensions.writable import (
    TgmountExtensionWritable,
    WritableDirConfig,
)
from tgmount.tgmount.root_config_reader import TgmountConfigReader
from tgmount.tgmount.tgmount_builderbase import (
    TgmountBuilderBase,
    TgmountBuilderExtensionProto,
)
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.util import yes


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
