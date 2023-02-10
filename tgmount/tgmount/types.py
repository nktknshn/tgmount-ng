from typing import Any, Mapping, Protocol

from telethon.tl.custom import Message

# from tgmount.tgmount.tgmount_builderbase import TgmountBuilderBase
from tgmount import config
from tgmount.tgmount.tgmount_resources import TgmountResources

TgmountRootType = Mapping


class TgmountBuilderExtensionProto(Protocol):
    async def extend_resources(
        self,
        # cfg: config.Config,
        builder,
        # builder: TgmountBuilderBase,
        # resources: TgmountResources,
    ):
        pass
