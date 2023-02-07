from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Mapping, Optional, TypeGuard
import pytest
import pytest_asyncio
from tests.helpers.mocked.mocked_message import (
    MockedMessageWithDocument,
    MockedMessageWithPhoto,
)

from tgmount.tgclient import TelegramFilesSource, DocId

from tgmount.tgclient.client_types import TgmountTelegramClientReaderProto
from tgmount.tgclient.guards import MessageDownloadable
from tgmount.tgclient.message_types import MessageProto
from tgmount.tgclient.source.document import get_document_input_location
from tgmount.tgclient.source.item import FileSourceItem
from tgmount.tgclient.source.photo import get_photo_input_location
from tgmount.tgclient.types import TypeInputFileLocation
from tgmount.util import yes

from tgmount.vfs.file import read_file_content_bytes
from ..helpers.mocked import (
    MockedClientReader,
    MockedTelegramStorage,
    random_file_reference,
)
from ..integrational.fixtures import FixtureFiles, files
from ..helpers.fixtures_common import set_logging, FixtureSetLogging


class Client(MockedClientReader):
    def __init__(self, storage: MockedTelegramStorage) -> None:
        super().__init__(storage)


@dataclass
class MockedFileSourceItem(FileSourceItem):
    id: DocId
    file_reference: bytes
    access_hash: int
    size: int
    input_location_func: Callable[
        ["MockedFileSourceItem", Optional[bytes]], TypeInputFileLocation
    ]

    def input_location(self, file_reference: Optional[bytes]):
        return self.input_location_func(self, file_reference)


class MockedFileSource(TelegramFilesSource):
    def __init__(
        self, client: TgmountTelegramClientReaderProto, request_size: int | None = None
    ) -> None:
        super().__init__(client, request_size)

    def is_message_downloadable(
        self, message: MessageProto
    ) -> TypeGuard[MessageDownloadable]:
        return bool(yes(message.document)) or bool(yes(message.photo))

    def get_filesource_item(self, message: MessageDownloadable) -> FileSourceItem:
        if yes(message.document):
            return MockedFileSourceItem(
                id=message.document.id,
                file_reference=message.document.file_reference,
                access_hash=message.document.access_hash,
                size=message.document.size,
                input_location_func=lambda item, ref, doc=message.document: get_document_input_location(
                    doc, ref
                ),
            )
        elif yes(message.photo):
            return MockedFileSourceItem(
                id=message.photo.id,
                file_reference=message.photo.file_reference,
                access_hash=message.photo.access_hash,
                size=message.photo.sizes[0].size,
                input_location_func=lambda item, ref, photo=message.photo: get_photo_input_location(
                    photo, "any", ref
                ),
            )

        raise ValueError(f"Invalid message type: {message}")


@pytest.mark.asyncio
async def test_file_reference_document(
    files: FixtureFiles, set_logging: FixtureSetLogging
):
    set_logging(logging.DEBUG)
    storage, [entity] = MockedTelegramStorage.create_from_entities_list(["entity1"])

    client = Client(storage)
    files_source = MockedFileSource(client)

    msg0 = await entity.document(files.Hummingbird)

    print(msg0.document.file_reference)

    msg0_content = files_source.file_content(msg0)

    assert await read_file_content_bytes(msg0_content) == await files.get_file_bytes(
        files.Hummingbird
    )

    storage.set_file_reference(msg0.document.id, random_file_reference())
    # print(msg0.document.file_reference)

    assert await read_file_content_bytes(msg0_content) == await files.get_file_bytes(
        files.Hummingbird
    )


@pytest.mark.asyncio
async def test_file_reference_photo(
    files: FixtureFiles, set_logging: FixtureSetLogging
):
    set_logging(logging.DEBUG)
    storage, [entity] = MockedTelegramStorage.create_from_entities_list(["entity1"])

    client = Client(storage)
    files_source = MockedFileSource(client)

    msg0 = await entity.photo(files.Hummingbird)

    print(msg0.photo.file_reference)

    msg0_content = files_source.file_content(msg0)

    assert await read_file_content_bytes(msg0_content) == await files.get_file_bytes(
        files.Hummingbird
    )

    storage.set_file_reference(msg0.photo.id, random_file_reference())

    assert await read_file_content_bytes(msg0_content) == await files.get_file_bytes(
        files.Hummingbird
    )

    storage.set_file_reference(msg0.photo.id, random_file_reference())
    assert await read_file_content_bytes(msg0_content) == await files.get_file_bytes(
        files.Hummingbird
    )
