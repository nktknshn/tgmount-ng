from typing import Mapping
from tgmount.error import TgmountError
import yaml


async def read_config_file(config: str) -> Mapping:
    try:
        with open(config, "r+") as f:
            return yaml.safe_load(f)
    except Exception as e:
        raise TgmountError(f"Error loading config file:\n\n{e}")
