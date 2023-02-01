import asyncio
import os
from argparse import ArgumentParser
from dataclasses import replace
from typing import Optional

import yaml

from tgmount.config import Config
from tgmount.config.config import ConfigParser
from tgmount.controlserver import ControlServer
from tgmount.tgmount.tgmount_builder import TgmountBuilder
from tgmount.error import TgmountError
from tgmount.tgmount.validator import ConfigValidator
from .logger import logger


def add_mount_config_arguments(command_mount: ArgumentParser):
    command_mount.add_argument("config", type=str)
    command_mount.add_argument(
        "--mount-dir", type=str, required=False, dest="mount_dir"
    )
    command_mount.add_argument(
        "--debug-fuse", default=False, action="store_true", dest="debug_fuse"
    )

    command_mount.add_argument("--min-tasks", default=10, type=int, dest="min_tasks")


async def mount_config(
    config_file: str,
    *,
    api_credentials: Optional[tuple[int, str]] = None,
    session: Optional[str] = None,
    mount_dir: Optional[str] = None,
    debug_fuse=False,
    run_server=False,
    min_tasks=10,
):
    builder = TgmountBuilder()
    validator = ConfigValidator(builder)

    if not os.path.exists(config_file):
        raise TgmountError(f"Missing config file: {config_file}")

    try:
        with open(config_file, "r+") as f:
            cfg_dict: dict = yaml.safe_load(f)
    except Exception as e:
        raise TgmountError(f"Error load config file:\n\n{e}")

    cfg = ConfigParser().parse_config(cfg_dict)

    await validator.verify_config(cfg)

    if session is not None:
        cfg.client = replace(cfg.client, session=session)

    if api_credentials is not None:
        logger.info(f"Using api credentials from os enviroment or args")
        cfg.client = replace(
            cfg.client, api_id=api_credentials[0], api_hash=api_credentials[1]
        )

    # if subfolder is not None:
    #     subfolder_root = cfg.root.content.get(subfolder)

    #     if subfolder_root is None:
    #         raise TgmountError(f"Invalid subfolder")

    tgm = await builder.create_tgmount(cfg)

    try:
        logger.info(f"Connecting Telegram")
        await tgm.client.auth()
    except Exception as e:
        # await tgm.client.disconnect()
        raise TgmountError(f"Error while authenticating the client: {e}")

    if not tgm.client.is_connected():
        raise TgmountError(
            f"Error while connecting the client. Check api_id and api_hash"
        )

    # client: TgmountTelegramClient = tgm.client

    # async def printa(c):
    #     print(c)

    # client.on_disconnected.subscribe(printa)

    if run_server:
        server_cor = ControlServer(tgm).start()
        server_task = asyncio.create_task(server_cor)

        mount_cor = tgm.mount(
            mount_dir=mount_dir, debug_fuse=debug_fuse, min_tasks=min_tasks
        )
        mount_task = asyncio.create_task(mount_cor)

        return await asyncio.wait(
            [mount_task, server_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    else:
        await tgm.mount(
            mount_dir=mount_dir,
            debug_fuse=debug_fuse,
            min_tasks=min_tasks,
        )
