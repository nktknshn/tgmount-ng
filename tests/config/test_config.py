import dataclasses
from typing import Any
import pytest
import yaml
import os
from pprint import pprint
from tgmount.config import *
from tgmount.config.config import ConfigReader


def test_config_reader():
    reader = ConfigReader.from_mapping(
        {
            "client": {
                "session": "1",
                "api_id": 123,
                "api_hash": "123",
            },
            "message_sources": {"source1": {"entity": "source1"}},
            "root": {},
        }
    )

    cfg = reader.read_config()

    assert cfg.client.api_hash == "123"
    assert cfg.client.request_size == None
