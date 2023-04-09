from typing import Type, TypeAlias, TypeVar
import telethon
from telethon import events

from tgmount.tgclient.message_reaction_event import MessageReaction

DocId = int
# Document = telethon.types.Document
# Photo = telethon.types.Photo
TypeMessagesFilter: TypeAlias = telethon.types.TypeMessagesFilter
TypeInputFileLocation: TypeAlias = telethon.types.TypeInputFileLocation
InputDocumentFileLocation: TypeAlias = telethon.types.InputDocumentFileLocation
InputPhotoFileLocation: TypeAlias = telethon.types.InputPhotoFileLocation
EntityId = str | int


NewMessageEvent: TypeAlias = events.NewMessage.Event
MessageDeletedEvent: TypeAlias = events.MessageDeleted.Event
MessageEditedEvent: TypeAlias = events.MessageEdited.Event
MessageReactionEvent: TypeAlias = MessageReaction.Event


TT = TypeVar("TT")


class TotalListTyped(list[TT]):
    total: int
