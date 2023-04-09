from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    Mapping,
    Protocol,
    Type,
    TypeGuard,
    TypeVar,
    TypedDict,
)

from tgmount import vfs
from tgmount.common.extra import Extra
from tgmount.tgclient.guards import *
from tgmount.tgclient.message_types import MessageId
from tgmount.tgclient.messages_collection import WithId
from tgmount.tgclient.types import DocId
from tgmount.util import nn, none_fallback
from .types import (
    FileContentProviderProto,
)
from .filefactorybase import FileFactoryBase, TryGetFunc, resolve_future_or_value

T = TypeVar("T", bound=WithId)

FileFactorySupportedTypes = (
    MessageWithMusic
    | MessageWithVoice
    | MessageWithSticker
    | MessageWithAnimated
    | MessageWithKruzhochek
    | MessageWithCompressedPhoto
    | MessageWithDocumentImage
    | MessageWithVideoFile
    | MessageWithVideo
    | MessageWithOtherDocument
    | MessageWithFilename
    | MessageDownloadable
    | T
)


# TelegramFileExtra = tuple[int | None, int | None]
class TelegramFileExtra(Protocol):
    extra_name: ClassVar[str] = "message"

    message_id: MessageId
    document_id: DocId | None


class FactoryProps(TypedDict, total=False):
    treat_as: list[str]
    filename_mapping: Mapping[MessageId, str]


def add_filename_mapping(message: T, filename: str, props: FactoryProps):
    filename_mapping = props.get("filename_mapping", {})

    return {
        **props,
        "filename_mapping": {**filename_mapping, message.id: filename},
    }


class FileFactoryDefault(FileFactoryBase[FileFactorySupportedTypes | T], Generic[T]):
    """Takes a telegram message and produces vfs.FileLike or vfs.FileContentProto"""

    def __init__(
        self,
        files_source: FileContentProviderProto,
        factory_props: FactoryProps | None = None
        # TODO filename mapper
        #
    ) -> None:
        super().__init__(factory_props=factory_props)

        self._files_source = files_source
        self._supported = {**self._supported}

    def update_factory_props(
        self, factory_props: FactoryProps | Callable[[FactoryProps], FactoryProps]
    ):
        if callable(factory_props):
            self._factory_props = factory_props(self._factory_props)
        else:
            self._factory_props = factory_props

    async def filename(
        self, supported_item: T, *, factory_props: FactoryProps | None = None
    ) -> str:
        if nn(factory_props) and "filename_mapping" in factory_props:
            custom_filename = factory_props["filename_mapping"].get(supported_item.id)

            if nn(custom_filename):
                return custom_filename

        return await super().filename(
            supported_item,
            factory_props=factory_props,
        )

    async def file_content(
        self,
        supported_item: FileFactorySupportedTypes,
        factory_props: FactoryProps | None = None,
    ) -> vfs.FileContentProto:
        if (
            get_file_content := self.get_cls_item(
                supported_item, factory_props=factory_props
            ).content
        ) is not None:
            return await resolve_future_or_value(get_file_content(supported_item))

        return self._files_source.file_content(supported_item)

    async def file(
        self,
        supported_item: FileFactorySupportedTypes,
        name=None,
        factory_props: FactoryProps | None = None,
    ) -> vfs.FileLike:
        creation_time = getattr(supported_item, "date", datetime.now())

        doc_id = (
            MessageDownloadable.document_or_photo_id(supported_item)
            if MessageDownloadable.guard(supported_item)
            else None
        )
        message_id = (
            supported_item.id if TelegramMessage.guard(supported_item) else None
        )

        file_like = vfs.FileLike(
            name=none_fallback(
                name,
                await resolve_future_or_value(
                    self.filename(supported_item, factory_props=factory_props)
                ),
            ),
            content=await resolve_future_or_value(
                self.file_content(supported_item, factory_props=factory_props)
            ),
            creation_time=creation_time,
        )

        file_like.extra.create(
            TelegramFileExtra.extra_name,
            content={
                "document_id": doc_id,
                "message_id": message_id,
            },
        )

        return file_like


FileFactoryDefault.register(
    klass=MessageWithCompressedPhoto,
    filename=MessageWithCompressedPhoto.filename,
)
FileFactoryDefault.register(klass=MessageWithMusic, filename=MessageWithMusic.filename)
FileFactoryDefault.register(klass=MessageWithVoice, filename=MessageWithVoice.filename)
FileFactoryDefault.register(
    klass=MessageWithSticker, filename=MessageWithSticker.filename
)
FileFactoryDefault.register(
    klass=MessageWithAnimated, filename=MessageWithAnimated.filename
)
FileFactoryDefault.register(
    klass=MessageWithKruzhochek, filename=MessageWithKruzhochek.filename
)
FileFactoryDefault.register(
    klass=MessageWithDocumentImage, filename=MessageWithDocumentImage.filename
)
FileFactoryDefault.register(
    klass=MessageWithVideoFile, filename=MessageWithVideoFile.filename
)
FileFactoryDefault.register(klass=MessageWithVideo, filename=MessageWithVideo.filename)
FileFactoryDefault.register(
    klass=MessageWithOtherDocument, filename=MessageWithOtherDocument.filename
)
FileFactoryDefault.register(
    klass=MessageWithFilename, filename=MessageWithFilename.filename
)
FileFactoryDefault.register(
    klass=MessageDownloadable, filename=MessageDownloadable.filename
)
