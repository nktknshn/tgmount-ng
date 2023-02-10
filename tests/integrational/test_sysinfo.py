import logging
import pytest
from tests.helpers.mocked.mocked_message import MockedReactions

import tgmount
from tests.integrational.helpers import mdict
from tests.helpers.config import create_config
from tests.integrational.context import Context
from tgmount.fs.operations import FileSystemOperations
from tgmount.tgmount.root_config_walker import TgmountRootConfigWalker
from tgmount.vfs.vfs_tree import VfsTree, VfsTreeDir

from .fixtures import *


@pytest.mark.asyncio
async def test_sysinfo(fixtures: Fixtures):
    ctx = Context.from_fixtures(fixtures)

    ctx.set_config(create_config(root={"source": "source1", "producer": "SysInfo"}))

    async def test():
        assert await ctx.listdir_set("/") == {"cache", "fs"}
        assert await ctx.listdir_set("/fs") == {"inodes"}

    await ctx.run_test(test)
