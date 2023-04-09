from typing import Mapping, Type

from tgmount.tgmount.vfs_tree_producer_types import VfsTreeDirProducerProto


class ProducersProviderBase:
    producers: Mapping[str, Type[VfsTreeDirProducerProto]]

    # def __init__(self):
    #     self._producers = {}

    def get_by_name(self, name: str) -> Type[VfsTreeDirProducerProto] | None:
        return self.producers.get(name)
