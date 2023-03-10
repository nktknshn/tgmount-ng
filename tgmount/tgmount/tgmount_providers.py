from typing import Any, Mapping, Type

from tgmount.cache import CacheMemory
from tgmount.tgmount.producers.producer_by_performer import VfsTreeGroupByPerformer
from tgmount.tgmount.producers.producer_by_forward import VfsTreeGroupByForward
from tgmount.tgmount.producers.producer_by_reaction import VfsTreeGroupByReactions
from tgmount.tgmount.producers.producer_by_sender import VfsTreeDirBySender
from tgmount.tgmount.producers.producer_plain import VfsTreeProducerPlainDir
from tgmount.tgmount.producers.producer_sysinfo import VfsTreeProducerSysInfo
from tgmount.tgmount.producers.producer_zip import VfsProducerZip
from tgmount.tgmount.vfs_tree_producer_types import VfsTreeProducerProto
from tgmount.tgmount.wrappers.wrapper_exclude_empty_dirs import WrapperEmpty
from .filters import (
    telegram_filters_to_filter_type,
    All,
    And,
    ByExtension,
    ByReaction,
    First,
    Last,
    Not,
    OnlyUniqueDocs,
    Seq,
    Union,
    from_context_classifier,
)
from .providers.provider_caches import CacheTypesProviderBase
from .providers.provider_filters import FilterProviderBase
from .providers.provider_vfs_wrappers import ProviderVfsWrappersBase
from .providers.provider_producers import ProducersProviderBase
from .wrappers.wrapper_zips_as_dirs import WrapperZipsAsDirs


class VfsWrappersProvider(ProviderVfsWrappersBase):
    wrappers = {
        "ExcludeEmptyDirs": WrapperEmpty,
        "ZipsAsDirs": WrapperZipsAsDirs,
    }


class CachesProvider(CacheTypesProviderBase):
    caches = {
        "memory": CacheMemory,  # type: ignore XXX
    }


class ProducersProvider(ProducersProviderBase):
    producers: Mapping[str, Type[VfsTreeProducerProto]] = {
        "PlainDir": VfsTreeProducerPlainDir,
        "BySender": VfsTreeDirBySender,
        "ByForward": VfsTreeGroupByForward,
        "ByPerformer": VfsTreeGroupByPerformer,
        "ByReactions": VfsTreeGroupByReactions,
        "SysInfo": VfsTreeProducerSysInfo,
        "UnpackedZip": VfsProducerZip,
    }


class FilterProvider(FilterProviderBase):
    telegram_filters = telegram_filters_to_filter_type
    filters = {
        "OnlyUniqueDocs": OnlyUniqueDocs,
        # "ByTypes": ByTypes,
        "All": All,
        "First": First,
        "Last": Last,
        "ByExtension": ByExtension,
        "Not": Not,
        "Union": Union,
        "Seq": Seq,
        "And": And,
        "ByReaction": ByReaction,
        **telegram_filters_to_filter_type
    }

    filter_getters = [
        from_context_classifier,
    ]
