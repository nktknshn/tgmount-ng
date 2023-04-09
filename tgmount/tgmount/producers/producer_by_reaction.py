from collections import defaultdict
from typing import Iterable, Mapping

import telethon
from tgmount.tgclient.guards import MessageForwarded, MessageWithReactions
from tgmount.tgclient.message_types import MessageProto, ReactionEmojiProto
from tgmount.tgmount.vfs_tree_producer_types import (
    VfsTreeDirProducerConfig,
    VfsTreeDirProducerProto,
)

from .grouperbase import GroupedMessages, VfsTreeProducerGrouperBase


async def group_by_reaction(
    reactions_messages: Iterable[MessageWithReactions],
) -> Mapping[str, list[MessageWithReactions]]:
    reactions: defaultdict[str, list[MessageWithReactions]] = defaultdict(list)

    for m in reactions_messages:
        for r in m.reactions.results:
            if not ReactionEmojiProto.guard(r.reaction):
                continue
            reactions[r.reaction.emoticon].append(m)

    return reactions


class VfsTreeGroupByReactions(VfsTreeProducerGrouperBase, VfsTreeDirProducerProto):
    @classmethod
    async def from_config(
        cls, resources, config: VfsTreeDirProducerConfig, arg: Mapping, sub_dir
    ):
        return VfsTreeGroupByReactions(
            config=config,
            dir_structure=arg.get(
                "dir_structure",
                VfsTreeGroupByReactions.DEFAULT_ROOT_CONFIG,
            ),
            resources=resources,
            tree_dir=sub_dir,
        )

    async def group_messages(
        self, messages: Iterable[MessageProto]
    ) -> GroupedMessages[MessageWithReactions]:
        return await group_by_reaction(filter(MessageWithReactions.guard, messages)), []
