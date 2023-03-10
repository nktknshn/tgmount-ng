from dataclasses import dataclass
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Generator,
    Mapping,
    Optional,
    TypedDict,
)

from tgmount import fs, vfs
from tgmount.tglog import init_logging


MountFsTreeProps = TypedDict(
    "Main1Props",
    debug=bool,
    fs_tree=vfs.DirContentSourceMapping,
)


async def mount_fs_tree_main(
    props: MountFsTreeProps,
    on_event,
):
    init_logging(props["debug"])
    return fs.FileSystemOperations(
        vfs.root(
            vfs.dir_content_from_tree(
                props["fs_tree"],
            )
        )
    )
