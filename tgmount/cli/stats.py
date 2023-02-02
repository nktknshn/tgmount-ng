import asyncio
import json
import os
from argparse import ArgumentParser, Namespace

from tgmount.controlserver.server import SOCKET_FILE


def print_output(obj, func, print_json=False):
    if print_json:
        print(json.dumps(obj))
    else:
        func(obj)


def print_inodes(inodes: list[tuple[int, list[str]]]):
    for inode, path_list in inodes:
        print(f"{inode}\t{os.path.join(*path_list)}")


import sys


async def stats(args: Namespace):
    for x in range(10000):
        print(x)

    # IMPORTANT: Flush stdout here, to ensure that the
    # SIGPIPE-triggered exception can be caught.
    sys.stdout.flush()


def add_stats_parser(command_stats: ArgumentParser):

    command_stats.add_argument("--socket-file", type=str, default=SOCKET_FILE)

    command_stats_subparsers = command_stats.add_subparsers(dest="stats_subcommand")

    command_stats_inodes = command_stats_subparsers.add_parser("inodes")

    command_stats_inodes.add_argument(
        "--paths", "-p", action="store_true", default=False
    )

    command_stats_inodes.add_argument("--json", action="store_true", default=False)

    command_stats_inodes_tree = command_stats_subparsers.add_parser("inodes-tree")
    command_stats_inodes_tree.add_argument("--json", action="store_true", default=False)
