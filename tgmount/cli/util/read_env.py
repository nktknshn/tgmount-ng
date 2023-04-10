import argparse
import os
from typing import Any, Optional, TypedDict

from tgmount.error import TgmountError

ReadosEnv = TypedDict(
    "_read_os_env",
    api_id=Optional[int],
    api_hash=Optional[str],
    session=Optional[str],
)


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
    os_env = read_os_env()

    api_id = os_env["api_id"]
    api_hash = os_env["api_hash"]
    session = os_env["session"]

    if args.tgapp is not None:
        api_id, api_hash = parse_tgapp_str(args.tgapp)

    if args.session is not None:
        session = args.session

    return session, api_id, api_hash


def get_tgapp_and_session(args: argparse.Namespace) -> tuple[str, int, str]:
    session, api_id, api_hash = try_get_tgapp_and_session(args)

    if session is None or api_id is None or api_hash is None:
        raise TgmountError(
            f"Missing either session or api_id or api_hash. Use TGAPP and SESSION environment variable or command line arguments to set them."
        )

    return session, api_id, api_hash
