from typing import Mapping, Sequence, Type
from tgmount import util, vfs, config
from tgmount.util import none_fallback, nn
from tgmount.util.timer import Timer

from .logger import module_logger as logger
from .root_config_walker import TgmountRootConfigWalker
from .root_config_types import RootConfigWalkingContext
from .tgmount_resources import TgmountResources
from .types import TgmountRootType
from tgmount.vfs.vfs_tree import VfsTree, VfsTreeDir
from .vfs_tree_producer_types import (
    VfsTreeDirProducerConfig,
    VfsTreeProducerExtensionProto,
    VfsDirConfig,
    VfsTreeDirProducerProto,
)


class VfsTreeProducer:
    """Class that using `TgmountResources` and `VfsStructureConfig` produces content into `VfsTreeDir` or `VfsTree`"""

    TgmountConfigReader = TgmountRootConfigWalker

    logger = logger.getChild(f"VfsTreeProducer")
    LOG_DEPTH = 2

    def __init__(
        self, extensions: Sequence[VfsTreeProducerExtensionProto] | None = None
    ) -> None:
        self._extensions = none_fallback(extensions, [])

    def __repr__(self) -> str:
        return f"VfsTreeProducer()"

    async def produce(
        self,
        resources: TgmountResources,
        dir_config: config.DirConfig,
        tree_dir: VfsTreeDir | VfsTree,
        ctx=None,
    ):
        """Produce content into `tree_dir` using `resources` and `dir_config`"""
        config_reader = self.TgmountConfigReader()

        t1 = Timer()
        t1.start("producer")

        async for (
            path,
            keys,
            vfs_dir_config,
            ctx,
        ) in config_reader.walk_config_with_ctx(
            dir_config,
            resources=resources,
            ctx=none_fallback(
                ctx,
                RootConfigWalkingContext.from_resources(resources),
            ),
        ):
            await self.produce_from_vfs_dir_config(
                resources, vfs_dir_config, path, tree_dir
            )

        t1.stop()

        # self.logger.trace(
        #     f"Done producing {tree_dir.path}. {t1.intervals[0].duration:.2f} ms"
        # )

    async def produce_from_vfs_dir_config(
        self,
        resources: TgmountResources,
        vfs_dir_config: VfsDirConfig,
        path: str,
        tree_dir: VfsTreeDir | VfsTree,
    ) -> VfsTreeDir:
        """Using `VfsDirConfig` produce content into `tree_dir`"""
        global_path = util.path.path_join(tree_dir.path, path)

        if len(util.path.napp(global_path, True)) <= self.LOG_DEPTH:
            self.logger.info(f"Producing {global_path}")
        else:
            self.logger.debug(f"Producing {global_path}")

        # create the subdir
        vfs_tree_dir = await tree_dir.create_dir(path)

        # If the directory has any wrapper
        if vfs_dir_config.vfs_wrappers is not None:
            for wrapper_cls, wrapper_arg in vfs_dir_config.vfs_wrappers:
                wrapper = wrapper_cls.from_config(
                    none_fallback(wrapper_arg, {}), vfs_tree_dir
                )
                vfs_tree_dir.add_wrapper(wrapper)

        # If the directory has any producer
        if (
            vfs_dir_config.vfs_producer is not None
            and vfs_dir_config.vfs_producer_config is not None
        ):
            # self.logger.debug(f"{sub_dir.path} uses {vfs_config.vfs_producer} producer")

            producer = await self.create_dir_producer(
                resources,
                vfs_dir_config.vfs_producer,
                vfs_dir_config.vfs_producer_config,
                none_fallback(vfs_dir_config.vfs_producer_arg, {}),
                global_path,
                vfs_tree_dir,
            )
            await producer.produce()

        for ext in self._extensions:
            await ext.extend_vfs_tree_dir(resources, vfs_dir_config, vfs_tree_dir)

        return vfs_tree_dir

    async def create_dir_producer(
        self,
        resources: TgmountResources,
        vfs_producer_klass: Type[VfsTreeDirProducerProto],
        vfs_producer_config: VfsTreeDirProducerConfig,
        vfs_producer_arg: Mapping,
        path: str,
        vfs_tree_dir: VfsTreeDir,
    ):
        return await vfs_producer_klass.from_config(
            resources,
            vfs_producer_config,
            vfs_producer_arg,
            vfs_tree_dir,
        )
