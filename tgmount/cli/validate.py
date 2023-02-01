from argparse import ArgumentParser, Namespace
from pprint import pprint
from tgmount import tglog
from tgmount.cli.util.config import read_config_file
from tgmount.config.config import ConfigParser, ConfigReader
from tgmount.config.error import ConfigError
from tgmount.config.helpers import assert_that
from tgmount.tgmount.validator import ConfigValidator
from tgmount.error import TgmountError

from tgmount.tgmount.tgmount_builder import TgmountBuilder
from tgmount.util import yes
from .logger import logger


def add_validate_arguments(command_validate: ArgumentParser):
    command_validate.add_argument("config", type=str)
    command_validate.add_argument("--root", action="store_true", default=False)


async def validate(args: Namespace):
    builder = TgmountBuilder()
    validator = ConfigValidator(builder)

    # if yes(, str):
    #     pass

    assert_that(
        isinstance(args.config, str),
        TgmountError(f"Invalid value for config arg: {args.config}"),
    )

    config_mapping = await read_config_file(args.config)

    # if yes(args.root, bool):
    #     validator.verify_root()

    # validator.verify_config(cfg)
    try:
        cfg = ConfigParser().parse_config(config_mapping)
    except ConfigError as e:
        logger.error(f"Error parsing config: {str(e)}")
        return 1
    try:
        await validator.verify_config(cfg)
    except ConfigError as e:
        logger.error(f"Error validating config: {str(e)}")
        return 1
    pprint("OK")
    logger.debug(cfg)
