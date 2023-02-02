from argparse import ArgumentParser, Namespace
import os

from tgmount import util
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
import aiofiles
from tgmount.tgclient.client import TgmountTelegramClient
from tgmount.tgclient.files_source import TelegramFilesSource
from tgmount.tgclient.guards import MessageDownloadable, MessageWithFilename
from tgmount.tgmount.tgmount_builder import MyFileFactoryDefault
from .logger import logger


def add_download_arguments(command_download: ArgumentParser):
    command_download.add_argument(
        "entity", type=util.int_or_string, help="Entity to download from"
    )
    command_download.add_argument(
        "--output-dir", "-O", type=str, default=".", help="Destination folder for files"
    )
    command_download.add_argument("ids", type=int, nargs="+", help="Messages ids")
    command_download.add_argument(
        "--keep-filename",
        action="store_true",
        default=False,
        dest="keep_filename",
        help="Keep original filenames",
    )
    command_download.add_argument(
        "--request_size",
        "-R",
        type=util.get_bytes_count,
        dest="request_size",
        default=256 * 1024,
        help="How much data to fetch per request",
    )


async def download(
    client: TgmountTelegramClient,
    args: Namespace,
):
    source = TelegramFilesSource(client, request_size=args.request_size)

    factory = MyFileFactoryDefault(files_source=source)

    messages = await client.get_messages(
        entity=args.entity,
        ids=args.ids,
    )

    for m in messages:
        if not MessageDownloadable.guard(m):
            logger.warning(f"{m.id} is not a downloadable message.")
            continue

        total_fetched = 0
        filelike = await factory.file(m)
        file_size = filelike.content.size

        if args.keep_filename and MessageWithFilename.guard(m):
            output_file_path = os.path.join(args.output_dir, m.file.name)
        else:
            output_file_path = os.path.join(args.output_dir, filelike.name)

        telegram_file = await filelike.content.open_func()
        output_file = await aiofiles.open(output_file_path, "wb")

        tq = tqdm(
            total=file_size,
            desc=output_file_path,
            unit="B",
            unit_divisor=1024,
            unit_scale=True,
            # leave=True,
            ascii=True,
        )

        while total_fetched < file_size:
            request_size = min(args.request_size, file_size - total_fetched)

            block = await filelike.content.read_func(
                telegram_file, total_fetched, request_size
            )

            await output_file.write(block)

            total_fetched += len(block)
            # print(".", end="", flush=True)
            # print(f"{file_size-total_fetched},", end="", flush=True)
            tq.update(len(block))

        tq.close()

        await output_file.close()
        await filelike.content.close_func(telegram_file)
