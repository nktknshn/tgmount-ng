from abc import abstractmethod
from typing import Protocol, Type, Mapping

from tgmount.cache import CacheInBlocksProto
from tgmount.error import TgmountError


class CachesTypesProviderProto(Protocol):
    @abstractmethod
    def as_mapping(self) -> Mapping[str, Type[CacheInBlocksProto]]:
        pass

    @abstractmethod
    def get_cache_type(self, cache_type: str) -> Type[CacheInBlocksProto]:
        pass

    @abstractmethod
    def has_cache_type(self, cache_type: str) -> bool:
        pass

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        pass


class CacheTypesProviderBase(CachesTypesProviderProto):
    caches: Mapping[str, Type[CacheInBlocksProto]]

    def as_mapping(self) -> Mapping[str, Type[CacheInBlocksProto]]:
        return self.caches

    @property
    def supported_types(self) -> list[str]:
        return list(self.caches.keys())

    def get_cache_type(self, cache_type: str) -> Type[CacheInBlocksProto]:
        cache = self.caches.get(cache_type)

        if cache is None:
            raise TgmountError(f"Missing cache with type: {cache_type}")

        return cache

    def has_cache_type(self, cache_type: str):
        return cache_type in self.caches

    # async def create_cache_factory(self, cache_type: str, **kwargs) -> CacheFactory:
    #     ...
