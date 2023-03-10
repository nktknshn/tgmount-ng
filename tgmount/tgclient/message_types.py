from abc import abstractmethod
from datetime import datetime
from typing import Any, Optional, Protocol, TypeGuard

import telethon

from tgmount.util import yes

MessageId = int
ChatId = str | int


class StickerProto(Protocol):
    pass


class VideoProto(Protocol):
    pass


class VideoNoteProto(Protocol):
    pass


class GifProto(Protocol):
    pass


class AudioProto(Protocol):
    pass


class VoiceProto(Protocol):
    pass


class ReactionEmojiProto(Protocol):
    emoticon: str


class ReactionCountProto(Protocol):
    reaction: ReactionEmojiProto
    count: int


class ReactionsProto(Protocol):
    results: list[ReactionCountProto]


class SenderProto(Protocol):
    username: str | None


class ForwardProto(Protocol):
    from_name: str | None
    from_id: int
    is_channel: bool
    is_group: bool

    @abstractmethod
    async def get_chat():
        ...


class FileProto(Protocol):
    name: str | None
    mime_type: str | None
    ext: str | None
    performer: str | None
    title: str | None
    duration: int | None


class MediaProto(Protocol):
    pass


class DocumentProto(Protocol):
    id: int
    size: int
    access_hash: int
    file_reference: bytes
    attributes: list

    @staticmethod
    def guard_document_image(document: "DocumentProto"):
        return (
            DocumentProto.get_attribute(
                document, telethon.types.DocumentAttributeImageSize
            )
            is not None
        )

    @staticmethod
    def get_attribute(doc: "DocumentProto", attr_cls) -> Optional[Any]:
        for attr in doc.attributes:
            if isinstance(attr, attr_cls):
                return attr


class PhotoSizeProtoBasic:
    type: str
    w: int
    h: int
    size: int


class PhotoSizeProtoProgressive:
    type: str
    w: int
    h: int
    sizes: list[int]


PhotoSizeProto = PhotoSizeProtoBasic | PhotoSizeProtoProgressive


class PhotoProto(Protocol):
    id: int
    access_hash: int
    file_reference: bytes
    sizes: list[PhotoSizeProto]

    @staticmethod
    def guard(photo: Any) -> TypeGuard["PhotoProto"]:
        return isinstance(photo, telethon.types.Photo)


class MessageProto(Protocol):
    id: MessageId
    chat_id: ChatId
    from_id: int | None
    text: str | None
    file: FileProto | None
    document: DocumentProto | None
    forward: ForwardProto | None
    photo: PhotoProto | None
    sticker: StickerProto | None
    video_note: VideoNoteProto | None
    video: VideoProto | None
    gif: GifProto | None
    audio: AudioProto | None
    voice: VoiceProto | None
    reactions: ReactionsProto | None
    date: datetime | None

    @abstractmethod
    async def get_sender() -> SenderProto:
        ...

    @staticmethod
    def guard(msg: Any):
        return hasattr(msg, "id")

    @staticmethod
    def repr_short(message: "MessageProto"):
        def fmt(text: str):
            return text[:10].replace("\n", "\\n")

        if yes(message.text):
            return f"Message(id={message.id}, message='{fmt(message.text)}...', document={bool(message.document)}, photo={bool(message.photo)})"

        return f"Message(id={message.id}, document={bool(message.document)}, photo={bool(message.photo)})"
