import traceback

import argparse
import logging

from tgmount import cli
from tgmount import main as main_settings
from tgmount.cli.util import get_client, get_tgapp_and_session

# import list_dialogs, list_documents, add_list_documents_arguments
from tgmount.main.util import run_main
from tgmount.tglog import init_logging
from tgmount.error import TgmountError

"""
export TGAPP=111111:ac7e6350d04adeadbeedf1af778773d6f0 TGSESSION=tgfs

tgmount auth [session]
tgmount list dialogs
tgmount list documents [entity]
tgmount mount [config] [mount_path] 
"""


def get_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument("--session", type=str, required=False)
    parser.add_argument("--tgapp", type=str, required=False)

    parser.add_argument("--debug", default=False, action="store_true")
    parser.add_argument(
        "--debug-fs-ops", default=False, action="store_true", dest="debug_fs_ops"
    )

    commands_subparsers = parser.add_subparsers(dest="command")

    command_auth = commands_subparsers.add_parser("auth")
    command_mount = commands_subparsers.add_parser("mount-config")
    command_mount_args = commands_subparsers.add_parser("mount")
    command_validate = commands_subparsers.add_parser("validate")
    command_stats = commands_subparsers.add_parser("stats")

    command_list = commands_subparsers.add_parser("list")
    command_list_subparsers = command_list.add_subparsers(dest="list_subcommand")

    command_list_dialogs = command_list_subparsers.add_parser("dialogs")
    command_list_documents = command_list_subparsers.add_parser("documents")

    cli.add_list_documents_arguments(command_list_documents)
    cli.add_mount_config_arguments(command_mount)
    cli.add_stats_parser(command_stats)
    cli.add_mount_arguments(command_mount_args)
    cli.add_validate_arguments(command_validate)

    return parser


async def main(loop):

    args = get_parser().parse_args()

    init_logging(
        debug_level=logging.DEBUG if args.debug else logging.INFO,
        debug_fs_ops=args.debug_fs_ops,
    )

    if args.command == "list" and args.list_subcommand == "dialogs":
        session, api_id, api_hash = get_tgapp_and_session(args)

        async with get_client(session, api_id, api_hash, loop=loop) as client:
            await cli.list_dialogs(client)

    elif args.command == "list" and args.list_subcommand == "documents":
        session, api_id, api_hash = get_tgapp_and_session(args)

        async with get_client(session, api_id, api_hash, loop=loop) as client:
            await cli.list_documents(
                client,
                args.entity,
                limit=args.limit,
                reverse=args.reverse,
                print_message_object=args.print_message_object,
                include_unsupported=args.include_unsupported,
                only_unsupported=args.only_unsupported,
                print_all_matching_types=args.print_all_matching_types,
                only_unique_docs=args.only_unique_docs,
            )

    elif args.command == "mount-config":
        session, api_id, api_hash = get_tgapp_and_session(args)
        # main_settings.run_forever = args.run_server

        api_credentials = (
            (api_id, api_hash) if api_id is not None and api_hash is not None else None
        )
        await cli.mount_config(
            args.config,
            api_credentials=api_credentials,
            session=args.session,
            mount_dir=args.mount_dir,
            debug_fuse=args.debug_fuse,
            min_tasks=args.min_tasks,
            # run_server=args.run_server,
        )
    elif args.command == "mount":
        session, api_id, api_hash = get_tgapp_and_session(args)

        api_credentials = (
            (api_id, api_hash) if api_id is not None and api_hash is not None else None
        )
        await cli.mount(
            args,
            api_credentials=api_credentials,
            session=session,
        )
    elif args.command == "stats":
        await cli.stats(args)
    elif args.command == "validate":
        await cli.validate(args)


if __name__ == "__main__":
    try:
        run_main(
            main,
            forever=main_settings.run_forever,
        )
    except TgmountError as e:
        print(f"Tgmount error happened: {e}")
    except Exception as e:
        print(f"Other exception happened: {e}")
        print(str(traceback.format_exc()))
