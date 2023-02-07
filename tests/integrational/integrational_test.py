import asyncio
import logging
from collections.abc import Awaitable, Callable
from os import stat_result
from typing import Any, AsyncGenerator, Iterable, Mapping

import aiofiles
from tests.helpers.mount_context import MountContext

import tgmount.config as config
from tests.helpers.mocked.mocked_storage import EntityId, MockedTelegramStorage
from tests.helpers.mount import handle_mount
from tests.helpers.config import create_config
from tgmount import tglog, vfs
from tgmount.config.config import ConfigParser
from tgmount.config.config_type import ConfigRootParserProto
from tgmount.config.types import Config, DirConfig
from tgmount.main.util import mount_ops
from tgmount.tgclient.guards import MessageWithText
from tgmount.tgmount.tgmount_builder import MyFileFactoryDefault, TgmountBuilder
from tgmount.tgmount.tgmountbase import TgmountBase, VfsTreeProducer
from tgmount.util import none_fallback

from ..helpers.fixtures_common import mnt_dir
from ..helpers.mocked.mocked_client import MockedClientReader, MockedClientWriter
from ..logger import logger as _logger


class MockedVfsTreeProducer(VfsTreeProducer):
    async def produce_path(self, tree_dir, path: str, vfs_config, ctx):
        # to test concurrent
        # await asyncio.sleep(0.1)
        return await super().produce_from_config(tree_dir, path, vfs_config)


class MockedTgmountBase(TgmountBase):
    ...


class MockedFileFactory(MyFileFactoryDefault):
    pass


MockedFileFactory.register(
    klass=MessageWithText,
    filename=MessageWithText.filename,
    file_content=lambda m: vfs.text_content(m.text),
)


class MockedTgmountBuilderBase(TgmountBuilder):
    TelegramClient = MockedClientReader
    VfsTreeProducer = MockedVfsTreeProducer
    TgmountBase = MockedTgmountBase
    FileFactory = MockedFileFactory

    def __init__(self, storage: MockedTelegramStorage) -> None:
        self._storage = storage

    async def create_client(self, cfg: config.Config, **kwargs):
        return self.TelegramClient(self._storage)


async def main_function(
    *,
    mnt_dir: str,
    cfg: config.Config,
    debug: int,
    storage: MockedTelegramStorage,
    builder_klass=MockedTgmountBuilderBase,
    shared: dict,
):
    test_logger = _logger.getChild("intergrational")
    test_logger.setLevel(debug)

    # tglog.getLogger("FileSystemOperations()").setLevel(logging.ERROR)
    # logging.getLogger("telethon").setLevel(logging.ERROR)

    test_logger.info("Building...")
    builder = builder_klass(storage=storage)

    test_logger.info("Creating resources...")
    tgm = await builder.create_tgmount(cfg)

    test_logger.info("Auth...")
    await tgm.client.auth()

    test_logger.info("Fetching messages...")
    await tgm.fetch_messages()

    test_logger.info("Creating FS...")
    await tgm.create_fs()

    test_logger.info("Unpausing events dispatcher")
    await tgm.events_dispatcher.resume()

    test_logger.info("Mounting FS")

    shared["builder"] = builder
    shared["tgm"] = tgm
    shared["fs"] = tgm.fs

    await mount_ops(
        tgm.fs,
        mount_dir=mnt_dir,
        min_tasks=10,
        fsname="tgmount_test_fs",
    )


async def run_test(mount_coro, test_coro):
    mount_task = asyncio.create_task(mount_coro, name="mount_task")
    test_task = asyncio.create_task(test_coro, name="test_task")

    done, pending = await asyncio.wait(
        [mount_task, test_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    if mount_task in done:
        try:
            done.pop().result()
        except Exception:
            # pytest.fail(f"Mount process finished before test")
            pending.pop().cancel()
            raise
    else:
        done.pop().result()
        pending.pop().cancel()


async def _run_test(
    test_func,
    *,
    mnt_dir: str,
    cfg: config.Config,
    storage: MockedTelegramStorage,
    builder_klass=MockedTgmountBuilderBase,
    debug: int,
    main_function=main_function,
    shared: dict,
):
    await run_test(
        main_function(
            mnt_dir=mnt_dir,
            cfg=cfg,
            storage=storage,
            debug=debug,
            builder_klass=builder_klass,
            shared=shared,
        ),
        test_func(),
    )


class TgmountIntegrationContext(MountContext):
    MockedTelegramStorage = MockedTelegramStorage
    MockedClientWriter = MockedClientWriter
    MockedTgmountBuilderBase = MockedTgmountBuilderBase

    def __init__(
        self,
        mnt_dir: str,
        *,
        caplog=None,
        default_config=None,
        config_parser: ConfigRootParserProto = ConfigParser(),
    ) -> None:
        self._mnt_dir = mnt_dir
        self.caplog = caplog

        self._default_config = none_fallback(
            default_config, create_config(config_reader=config_parser)
        )
        self.config_parser = config_parser
        self._storage = self.create_storage()
        self._client = self.create_client()
        self._debug = False
        self.main_function = main_function
        self.shared = {}

    @property
    def storage(self):
        return self._storage

    @property
    def mnt_dir(self):
        return self._mnt_dir

    @property
    def client(self):
        return self._client

    def set_config(self, config: Config):
        self._default_config = config

    def create_config(self, root: DirConfig):
        return self._default_config.set_root(root)

    def create_storage(self):
        return self.MockedTelegramStorage()

    def create_client(self):
        return self.MockedClientWriter(storage=self._storage)

    def get_root(self, root_cfg: Mapping) -> Mapping:
        return root_cfg

    def mount_task_root(self, root: DirConfig, debug=True):
        return self.mount_task(self.create_config(root), debug=debug)

    def mount_task(self, cfg: config.Config, debug=True):
        return asyncio.create_task(
            main_function(
                mnt_dir=self.mnt_dir,
                cfg=cfg,
                storage=self.storage,
                debug=debug,
                shared=self.shared,
            )
        )

    async def run_test(
        self,
        test_func: Callable[[], Awaitable[Any]],
        # config_reader: ConfigRootParserProto,
        cfg_or_root: config.Config | DirConfig | Mapping | None = None,
        # debug=None,
    ):
        # _debug = self.debug
        # self.debug = none_fallback(debug, self.debug)

        if isinstance(cfg_or_root, Mapping):
            cfg_or_root = self.config_parser.parse_root(cfg_or_root)

        # print(cfg_or_root.other_keys["source1"])
        cfg = self._get_config(cfg_or_root)

        for ms in cfg.message_sources.sources.values():
            self.storage.create_entity(ms.entity)

        await _run_test(
            handle_mount(self.mnt_dir)(test_func),
            mnt_dir=self.mnt_dir,
            cfg=cfg,
            storage=self.storage,
            debug=self.debug,
            main_function=self.main_function,
            builder_klass=self.MockedTgmountBuilderBase,
            shared=self.shared,
        )
        # self.debug = _debug

    def _get_config(
        self,
        cfg_or_root: config.Config | DirConfig | Mapping | None = None,
    ):
        cfg_or_root = none_fallback(cfg_or_root, self._default_config)

        if isinstance(cfg_or_root, Mapping):
            cfg_or_root = self.config_parser.parse_root(cfg_or_root)

        return (
            cfg_or_root
            if isinstance(cfg_or_root, config.Config)
            else self.create_config(cfg_or_root)
        )

    async def create_tgmount(
        self,
        cfg_or_root: config.Config | DirConfig | None = None,
    ) -> TgmountBase:
        builder = MockedTgmountBuilderBase(storage=self.storage)
        tgm = await builder.create_tgmount(self._get_config(cfg_or_root))

        return tgm
