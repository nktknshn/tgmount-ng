import argparse
import os
from typing import Any, Optional, TypedDict

from tgmount.error import TgmountError
from tgmount.util import yes

from .logger import logger

ReadosEnv = TypedDict(
    "_read_os_env",
    api_id=Optional[int],
    api_hash=Optional[str],
    session=Optional[str],
)


def try_read_from_file(tgapp_file="tgapp.txt"):
    if os.path.exists(tgapp_file):
        try:
            with open(tgapp_file, "r") as f:
                [api, hash] = f.read().split(":")

                api_id = int(api)
                api_hash = hash

                return api_id, api_hash
        except Exception:
            return (None, None)

    return (None, None)


def parse_tgapp_str(TGAPP: str):
    """format: 111111:ac7e6350d04adeadbeedf1af778773d6f0"""
    try:
        api_id, api_hash = TGAPP.split(":")
        api_id = int(api_id)
    except ValueError:
        raise TgmountError(f"Incorrect value for TGAPP env variable: {TGAPP}")

    return api_id, api_hash


def read_os_env(TGAPP="TGAPP", TGSESSION="TGSESSION") -> ReadosEnv:
    TGAPP = os.environ.get(TGAPP)
    TGSESSION = os.environ.get(TGSESSION)

    api_id = None
    api_hash = None

    if TGAPP is not None and TGAPP != "":
        api_id, api_hash = parse_tgapp_str(TGAPP)

    return ReadosEnv(
        api_id=api_id,
        api_hash=api_hash,
        session=TGSESSION,
    )


def try_get_tgapp_and_session(
    args: argparse.Namespace,
) -> tuple[str | None, int | None, str | None]:
    """Tries to read api credentials and session file name from args or os environment"""

    api_id = api_hash = None

    f_api_id, f_api_hash = try_read_from_file("tgapp.txt")

    if yes(f_api_id) and yes(f_api_hash):
        logger.debug('Got credentials from tgapp.txt')
        api_id = f_api_id
        api_hash = f_api_hash

    os_env = read_os_env()

    if yes(os_env["api_id"]) and yes(os_env["api_hash"]):
        logger.debug('Got credentials from os environment')
        api_id = os_env["api_id"]
        api_hash = os_env["api_hash"]

    session = os_env["session"]

    if args.tgapp is not None:
        logger.debug('Got credentials from args')
        api_id, api_hash = parse_tgapp_str(args.tgapp)

    if args.session is not None:
        session = args.session

    return session, api_id, api_hash


def get_tgapp_and_session(args: argparse.Namespace) -> tuple[str, int, str]:
    """Tries to read api credentials and session file name from args or os environment throwing an exception if they were not defined"""
    session, api_id, api_hash = try_get_tgapp_and_session(args)

    if session is None or api_id is None or api_hash is None:
        raise TgmountError(
            f"Missing either session or api_id or api_hash. Use TGAPP and SESSION environment variable or command line arguments to set them."
        )

    return session, api_id, api_hash
