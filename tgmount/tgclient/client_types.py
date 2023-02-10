from abc import abstractmethod
from typing import Any, Awaitable, Callable, Protocol, Sequence, TypeVar, Union

from telethon import events
from tgmount.tgclient.types import EntityId
from tgmount.tgclient.guards import MessageDownloadable

from tgmount.tgclient.message_reaction_event import MessageReactionEvent
from tgmount.tgclient.message_types import MessageProto

from .types import InputDocumentFileLocation, InputPhotoFileLocation, TotalListTyped

ListenerNewMessages = Callable[[events.NewMessage.Event], Awaitable[None]]
ListenerRemovedMessages = Callable[[events.MessageDeleted.Event], Awaitable[None]]
ListenerEditedMessage = Callable[
    [events.MessageEdited.Event | MessageReactionEvent], Awaitable[None]
]
from telethon import types

types.messages.AffectedMessages

T = TypeVar("T")


class TgmountTelegramClientEventProto(Protocol):
    @abstractmethod
    def subscribe_new_messages(self, listener: ListenerNewMessages, chats):
        pass

    @abstractmethod
    def subscribe_removed_messages(self, listener: ListenerRemovedMessages, chats):
        pass

    @abstractmethod
    def subscribe_edited_message(self, listener: ListenerEditedMessage, chats):
        pass


class TgmountTelegramClientGetMessagesProto(Protocol):
    @abstractmethod
    async def get_messages(
        self,
        *args,
        **kwargs,
    ) -> TotalListTyped[MessageProto]:
        pass


class IterDownloadProto(Protocol):
    @abstractmethod
    def __aiter__(self) -> "IterDownloadProto":
        pass

    @abstractmethod
    async def __anext__(self) -> bytes:
        pass


class TgmountTelegramClientIterDownloadProto(Protocol):
    @abstractmethod
    def iter_download(
        self,
        input_location: Union[InputPhotoFileLocation, InputDocumentFileLocation],
        *,
        offset: int,
        request_size: int,
        limit: int,
        file_size: int,
    ) -> IterDownloadProto:
        pass


class TgmountTelegramClientSendFileProto(Protocol):
    """async def send_file(
    self: 'TelegramClient',
    entity: 'hints.EntityLike',
    file: 'typing.Union[hints.FileLike, typing.Sequence[hints.FileLike]]',
    *,
    caption: typing.Union[str, typing.Sequence[str]] = None,
    force_document: bool = False,
    file_size: int = None,
    clear_draft: bool = False,
    progress_callback: 'hints.ProgressCallback' = None,
    reply_to: 'hints.MessageIDLike' = None,
    attributes: 'typing.Sequence[types.TypeDocumentAttribute]' = None,
    thumb: 'hints.FileLike' = None,
    allow_cache: bool = True,
    parse_mode: str = (),
    formatting_entities: typing.Optional[typing.List[types.TypeMessageEntity]] = None,
    voice_note: bool = False,
    video_note: bool = False,
    buttons: typing.Optional['hints.MarkupLike'] = None,
    silent: bool = None,
    background: bool = None,
    supports_streaming: bool = False,
    schedule: 'hints.DateLike' = None,
    comment_to: 'typing.Union[int, types.Message]' = None,
    ttl: int = None,
    **kwargs) -> 'types.Message':"""

    @abstractmethod
    async def send_file(
        self,
        entity: EntityId,
        file: bytes,
        *,
        force_document: bool = False,
        file_size: int | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        #     attributes: 'typing.Sequence[types.TypeDocumentAttribute]' = None,
        attributes: Sequence[Any] | None = None,
        background: bool | None = None,
        supports_streaming: bool = False,
    ) -> MessageDownloadable:
        pass


class TgmountTelegramClientDeleteMessagesProto(Protocol):
    @abstractmethod
    async def delete_messages(
        self,
        entity: EntityId,
        message_ids: list[int],
        *,
        revoke: bool = True,
    ) -> Sequence[types.messages.AffectedMessages]:
        # ) -> "typing.Sequence[types.messages.AffectedMessages]":
        pass


class TgmountTelegramClientSendMessageProto(Protocol):
    @abstractmethod
    async def send_message(self, entity: EntityId, message: str):
        pass


class TgmountTelegramClientReaderProto(
    TgmountTelegramClientGetMessagesProto,
    TgmountTelegramClientEventProto,
    TgmountTelegramClientIterDownloadProto,
    Protocol,
):
    """Interface for client that can fetch messages, download them and receive updates"""

    @abstractmethod
    def __init__(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    async def auth(self):
        pass


class TgmountTelegramClientWriterProto(
    TgmountTelegramClientSendMessageProto,
    TgmountTelegramClientDeleteMessagesProto,
    TgmountTelegramClientSendFileProto,
):
    pass


class TgmountTelegramClientProto(
    TgmountTelegramClientReaderProto,
    TgmountTelegramClientWriterProto,
):
    pass
