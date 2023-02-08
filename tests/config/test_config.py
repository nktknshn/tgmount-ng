import dataclasses
from typing import Any
import pytest
import yaml
import os
from pprint import pprint
from tgmount.config import *
from tgmount.config.config import ConfigParser, ConfigReader

from .fixtures import config_from_file


def test_reader1():
    reader = ConfigReader.from_mapping(
        {
            "client": {
                "session": "123",
                "api_id": 123,
                "api_hash": "1234",
            }
        }
    )
