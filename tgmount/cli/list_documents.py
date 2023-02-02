from argparse import ArgumentParser, Namespace
from typing import Any, Optional, TypedDict

import json
from tgmount.cli.mount import add_get_messages_args
from tgmount.tgclient.fetcher import TelegramMessagesFetcher

from tgmount import tgclient
from tgmount import util
from tgmount.tgclient import TgmountTelegramClient
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgmount.file_factory.classifier import ClassifierDefault
from tgmount.tgmount.filters import OnlyUniqueDocs
from tgmount.tgmount.tgmount_builder import MyFileFactoryDefault


class OutputRecord:
    id: int
    document_id: int | None
    types_str: str
    size: int
    filename: str
    original_filename: str | None
    text: str | None
    message_object: str | None
    date: str | None


class OutputRecordUnsupported:
    id: int
    # file: FileProto | None
    # document: DocumentProto | None
    # media: MediaProto | None
    message_object: str


Record = OutputRecord | OutputRecordUnsupported


class RecordEncoder(json.JSONEncoder):
    def default(self, o: Any):
        if isinstance(o, OutputRecord):
            record_dict = {}
            for header in ListDocumentsOutput.HEADERS:
                record_dict[header] = getattr(o, header)

            return record_dict

        return super().default(o)


class ListDocumentsOutput:
    TEXT_LIMIT = 20
    HEADERS = [
        "id",
        "document_id",
        # "filename",
        "original_filename",
        "text",
        "size",
        "date",
        "types_str",
    ]

    def __init__(self) -> None:
        self.records: list[Record] = []

    def append(self, record: Record):
        self.records.append(record)

    def print(self, only_unsupported=False, include_unsupported=False):
        rows = []
        columns_width = {k: len(k) for k in self.HEADERS}

        for record in self.records:
            if isinstance(record, OutputRecord):
                if only_unsupported:
                    continue
                row = []
                for prop in self.HEADERS:

                    value = getattr(record, prop)
                    formatter = getattr(self, f"format_{prop}", None)

                    if formatter is not None:
                        value_str = formatter(value)
                    else:
                        value_str = str(getattr(record, prop))

                    row.append(value_str)
                    columns_width[prop] = max(len(value_str), columns_width[prop])

                rows.append(row)

                if util.yes(record.message_object):
                    rows.append([record.message_object])

            elif include_unsupported or only_unsupported:
                rows.append([f"Unsupported: {record.id}\t{record.message_object}"])

        if len(rows) == 0:
            return

        rows = [self.HEADERS, *rows]

        for row in rows:
            if len(row) > 1:
                for width, value in zip(columns_width.values(), row):
                    print(value.ljust(width + 2), end="", flush=True)
                print()
            elif len(row) == 1:
                print(row[0])

    def print_unsupported(self):
        for record in self.records:
            if isinstance(record, OutputRecordUnsupported):
                print(record)

    def print_json(self):
        print(
            json.dumps(
                [rec for rec in self.records if isinstance(rec, OutputRecord)],
                cls=RecordEncoder,
            )
        )

    def format_text(self, text: str | None):
        if util.yes(text) and len(text) > 0:
            if len(text) > self.TEXT_LIMIT:
                return text[: self.TEXT_LIMIT].replace("\n", "\\n") + "..."
            else:
                return text
        else:
            return "None"


async def list_documents(
    client: TgmountTelegramClient,
    args: Namespace,
):
    factory = MyFileFactoryDefault(
        files_source=tgclient.TelegramFilesSource(client),
    )

    classifier = ClassifierDefault()

    tg_filter = None
    if util.yes(args.filter, str):
        filter_class = TelegramMessagesFetcher.FILTERS.get(args.filter)
        tg_filter = filter_class

    messages = await client.get_messages(
        entity=args.entity,
        reverse=args.reverse,
        filter=tg_filter,
        from_user=args.from_user,
        limit=args.limit,
        max_id=args.max_id,
        min_id=args.min_id,
        offset_date=args.offset_date,
        offset_id=args.offset_id,
        reply_to=args.reply_to,
        wait_time=args.wait_time,
    )

    result = ListDocumentsOutput()

    if args.only_unique_docs:
        messages = await OnlyUniqueDocs().filter(
            filter(MessageDownloadable.guard, messages)
        )

    for m in messages:
        message_record = OutputRecord()
        classes = classifier.classify_str(m)

        if factory.supports(m):

            types_str = (
                ",".join(classes)
                if args.print_all_matching_types
                else factory.get_cls(m).__name__
            )

            original_fname = (
                f"{m.file.name}"
                if m.file is not None and m.file.name is not None
                else None
            )

            document_id = (
                MessageDownloadable.document_or_photo_id(m)
                if MessageDownloadable.guard(m)
                else None
            )

            # if print_sender:
            #     sender = await m.get_sender()
            #     print(sender.username)
            filename = await factory.filename(m)
            size = await factory.size(m)

            message_record.id = m.id
            message_record.document_id = document_id
            message_record.types_str = types_str
            message_record.size = size
            message_record.filename = filename
            message_record.original_filename = original_fname
            message_record.text = m.text

            message_record.date = util.map_none(
                m.date, lambda d: d.strftime("%d/%m/%Y %H:%M:%S")
            )

            if args.print_message_object:
                message_record.message_object = str(m)
            else:
                message_record.message_object = None

            result.append(message_record)

            # if args.print_message_object:
            #     print(m)
        else:
            record = OutputRecordUnsupported()
            record.id = m.id
            record.message_object = str(m)
            result.append(record)

    if args.json:
        result.print_json()
    else:
        result.print(
            only_unsupported=args.only_unsupported,
            include_unsupported=args.include_unsupported,
        )

    # if args.include_unsupported or args.only_unsupported:
    #     result.print_unsupported()


def add_list_documents_arguments(command_list_documents: ArgumentParser):
    command_list_documents.add_argument("entity", type=util.int_or_string)
    add_get_messages_args(command_list_documents)

    command_list_documents.add_argument(
        "--json",
        "-j",
        dest="json",
        action="store_true",
        default=False,
        help="Print is json format",
    )

    command_list_documents.add_argument(
        "--print-message",
        "-p",
        dest="print_message_object",
        action="store_true",
        default=False,
        help="Include stringified message object in the output",
    )
    command_list_documents.add_argument(
        "--include-unsupported",
        "-u",
        dest="include_unsupported",
        action="store_true",
        default=False,
        help="Include messages that are unsupported for mounting",
    )

    command_list_documents.add_argument(
        "--only-unsupported",
        "-U",
        dest="only_unsupported",
        action="store_true",
        default=False,
        help="Only print messages that are unsupported for mounting",
    )

    command_list_documents.add_argument(
        "--all-types",
        "-t",
        dest="print_all_matching_types",
        action="store_true",
        default=False,
        help="Print all matching message classes",
    )

    command_list_documents.add_argument(
        "--only-unique-docs",
        "-q",
        dest="only_unique_docs",
        action="store_true",
        default=False,
        help="Exclude duplicate documents",
    )
