import abc
import functools

from tgmount import config
from tgmount.config.config import ConfigParser
from tgmount.config.error import ConfigError, ConfigErrorWithPath
from tgmount.tgclient.fetcher import TelegramMessagesFetcher
from tgmount.tgmount.tgmount_builderbase import TgmountBuilderBase
from tgmount.tgmount.tgmount_types import TgmountResources
from tgmount.util import no, yes

from .logger import logger

telegram_filters = TelegramMessagesFetcher.FILTERS


class ConfigValidatorError(ConfigErrorWithPath):
    pass


class ConfigValidatorBase:
    """The task for this class is to verify config before fetching messages."""

    logger = logger.getChild(f"ConfigValidatorBase")

    def __init__(self, builder: TgmountBuilderBase) -> None:
        self._builder = builder

    async def verify_config(self, cfg: config.Config):
        client = await self._builder.create_client(cfg)
        resources = await self._builder.create_tgmount_resources(client, cfg)
        await self.verify_client(cfg)
        await self.verify_message_sources(cfg)
        await self.verify_caches(cfg)
        await self.verify_root(resources, cfg)

    async def verify_client(self, cfg: config.Config):
        pass

    async def verify_message_sources(self, cfg: config.Config):
        for src_id, src in cfg.message_sources.sources.items():
            if not yes(src.filter):
                continue

            pass

    async def verify_caches(self, cfg: config.Config):

        if not yes(cfg.caches):
            return

        for cache_id, cache in cfg.caches.caches.items():
            pass

    async def verify_root(self, resources: TgmountResources, cfg: config.Config):
        await self.verify_filters(resources, "/", cfg.root)

    def _parse_filter(
        self, resources: TgmountResources, filter_value: config.FilterConfigValue
    ):
        parse_filter = functools.partial(self._parse_filter, resources)

        for filter_name, filter_arg in ConfigParser().parse_filter_value(filter_value):
            filter_class = resources.filters_provider.get(filter_name)

            if yes(filter_class):
                filter_class.from_config(
                    filter_arg,
                    resources,
                    parse_filter,
                )
            else:
                raise ConfigError(f"Missing filter {filter_name} in providers")

    async def verify_filters(
        self, resources: TgmountResources, key: str, dir_cfg: config.DirConfig
    ):
        """ """
        # self.logger.debug(f"verify_filters({key})")

        filter_prop = dir_cfg.filter
        parse_filter = functools.partial(self._parse_filter, resources)

        if yes(filter_prop):
            for filter_name, filter_arg in filter_prop.filter:
                filter_class = resources.filters_provider.get(filter_name)

                if yes(filter_class):
                    try:
                        filter_class.from_config(
                            filter_arg,
                            resources,
                            parse_filter,
                        )
                    except ConfigError as e:
                        raise ConfigError(f"Error creating {filter_name}: {str(e)}")
                else:
                    raise ConfigError(f"Missing filter {filter_name} in providers")

        for key, key_dir in dir_cfg.other_keys.items():
            await self.verify_filters(resources, key, key_dir)
