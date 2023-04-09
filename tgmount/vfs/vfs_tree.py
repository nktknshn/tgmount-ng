from collections.abc import Mapping, Sequence
from typing import Any, Awaitable, Union

from tgmount import vfs
from tgmount.common.extra import Extra
from tgmount.common.subscribable import (
    Subscribable,
    SubscribableListener,
    SubscribableProto,
)
from tgmount.tglog import TgmountLogger
from tgmount.util import none_fallback
from tgmount.util.col import map_keys
from tgmount.vfs.vfs_tree_subdirs import SubdirsRegistry

from .logger import module_logger as _logger
from .vfs_tree_types import (
    TreeEventNewDirs,
    TreeEventNewItems,
    TreeEventRemovedDirs,
    TreeEventRemovedItems,
    TreeEventType,
    TreeEventUpdatedItems,
    VfsTreeError,
    VfsTreeNotFoundError,
    VfsTreeProto,
)
from .vfs_tree_wrapper_types import VfsTreeWrapperProto
from tgmount import util


class VfsTreeDirContentProto(vfs.DirContentProto):
    tree: "VfsTree"
    path: str
    vfs_dir: Awaitable["VfsTreeDir"]


class VfsTreeDirContent(vfs.DirContentProto):
    """`vfs.DirContentProto` sourced from dir stored in `VfsTree` at `path`."""

    logger = _logger.getChild("VfsTreeDirContent")

    def __init__(self, tree: "VfsTree", path: str) -> None:
        self._tree = tree
        self._path = path

        self._logger = VfsTreeDirContent.logger.getChild(path, suffix_as_tag=True)
        # print(f"VfsTreeDirContent.init({self._path})")

    @property
    async def vfs_dir(self) -> "VfsTreeDir":
        return await self._tree.get_dir(self._path)

    @property
    def tree(self) -> "VfsTree":
        return self._tree

    @property
    def path(self) -> str:
        return self._path

    def __repr__(self) -> str:
        return f"VfsTreeDirContent({self._path})"

    async def _dir_content(self) -> vfs.DirContentProto:
        return await self._tree._get_dir_content(self._path)

    async def readdir_func(self, handle, off: int):
        self._logger.debug(
            f"ProducedContentDirContent({self._path}).readdir_func({off})"
        )
        return await (await self._dir_content()).readdir_func(handle, off)

    async def opendir_func(self):
        self._logger.debug(
            f"ProducedContentDirContent({self._path}).opendir_func()",
        )
        return await (await self._dir_content()).opendir_func()

    async def releasedir_func(self, handle):
        self._logger.debug(
            f"ProducedContentDirContent({self._path})" ".releasedir_func()"
        )
        return await (await self._dir_content()).releasedir_func(handle)


class VfsTreeDirMixin:
    _logger: TgmountLogger

    async def _update_content(
        self: "VfsTreeDir",  # type: ignore
        content: Mapping[str, vfs.DirContentItem],
    ):
        result = []

        for item in self._dir_content_items:
            if item.name in content:
                result.append(content[item.name])
            else:
                result.append(item)

        self._dir_content_items = result

    async def _put_content(
        self: "VfsTreeDir",  # type: ignore
        content: Sequence[vfs.DirContentItem],
        *,
        replace=False,
    ):
        if replace:
            self._dir_content_items = list(content)
        else:
            self._dir_content_items.extend(content)

    async def _get_dir_content_items(self: "VfsTreeDir"):  # type: ignore
        return self._dir_content_items[:]

    async def _remove_from_content(
        self,
        item: vfs.DirContentItem,
    ):
        try:
            self._dir_content_items.remove(item)
        except ValueError:
            self._logger.error(
                f"Error removing {item} from {self}. Element not found: content: "
                f"{self._dir_content_items}"
            )


class VfsTreeDir(VfsTreeDirMixin):
    """
    Represents a single dir.

    Stores a vfs.DirContentItem list,  a list of wrappers and Extra object.
    """

    logger = _logger.getChild("VfsTreeDir")

    def __init__(
        self,
        tree: "VfsTree",
        path: str,
        wrappers=None,
        extra: Extra | None = None,
    ) -> None:
        self._parent_tree = tree
        self._path = path
        self._dir_content_items: list[vfs.DirContentItem] = []
        self._wrappers: list[VfsTreeWrapperProto] = none_fallback(wrappers, [])

        self._logger = self.logger.getChild(self.path, suffix_as_tag=True)
        self.extra = extra

    def add_wrapper(self, w: VfsTreeWrapperProto):
        self._wrappers.append(w)

    async def child_updated(self, events: list[TreeEventType["VfsTreeDir"]]):
        """Method used by subdirs to notify the dir about its modifications.
        If this dir contains any wrappers updates are wrapped with `wrap_updates`
        method."""

        # self._logger.debug(f"child_updated( {events})")

        parent = await self.get_parent()

        for w in self._wrappers:
            events = await w.wrap_events(events)

        await parent.child_updated(events)

    async def get_parent(self):
        if self.path == "/":
            return self._parent_tree

        return await self._parent_tree.get_parent(self._path)

    def __repr__(self) -> str:
        return f"VfsTreeDir(path={self._path})"

    @property
    def tree(self) -> "VfsTree":
        return self._parent_tree

    @property
    def name(self):
        return util.path.split_path(self._path)[1]

    @property
    def path(self):
        """Dir global path"""
        return self._path

    def _globalpath(self, subpath: str):
        if subpath == "/":
            return self._path

        return util.path.path_join(self._path, util.path.path_remove_slash(subpath))

    async def get_subdir(self, subpath: str) -> "VfsTreeDir":
        return await self._parent_tree.get_dir(self._globalpath(subpath))

    async def get_subdirs(self, subpath: str = "/") -> list["VfsTreeDir"]:
        return await self._parent_tree.get_subdirs(self._globalpath(subpath))

    async def get_dir_content_items(
        self, subpath: str = "/"
    ) -> list[vfs.DirContentItem]:
        return await self._parent_tree.get_dir_content_items(
            self._globalpath(subpath),
        )

    async def create_dir(self, subpath: str) -> "VfsTreeDir":
        return await self._parent_tree.create_dir(self._globalpath(subpath))

    async def put_dir(self, d: "VfsTreeDir") -> "VfsTreeDir":
        return await self._parent_tree.put_dir(d)

    async def update_content(
        self,
        content: Mapping[str, vfs.DirContentItem],
        subpath: str = "/",
    ):
        await self._parent_tree.update_content(content, self._globalpath(subpath))

    async def put_content(
        self,
        content: Sequence[vfs.DirContentItem] | vfs.DirContentItem,
        subpath: str = "/",
        *,
        replace=False,
        notify=True,
    ):
        if not isinstance(content, Sequence):
            content = [content]

        await self._parent_tree.put_content(
            content, self._globalpath(subpath), replace=replace, notify=notify
        )

    async def remove_subdir(self, subpath: str):
        await self._parent_tree.remove_dir(self._globalpath(subpath))

    async def get_by_name(
        self,
        file_name: str,
        subpath: str = "/",
    ):
        items = await self._parent_tree.get_dir_content_items(
            self._globalpath(subpath),
        )

        for item in items:
            if item.name == file_name:
                return item

    async def remove_content(
        self,
        item: vfs.DirContentItem,
        subpath: str = "/",
    ):
        self._logger.debug(f"remove_content({item}, subpath={subpath})")
        await self._parent_tree.remove_content(self._globalpath(subpath), item)

    async def get_dir_content(self):
        return await self.tree.get_dir_content(self.path)


class VfsTree(Subscribable, VfsTreeProto):
    """
    The structure that holds the whole generated FS tree.
    Producers use it to read and write the structures they are responsible for.

    Storing dirs in a single mapping we try to avoid recursiveness.

    Provides interface for accessing dirs and their contents by their global paths.
    """

    logger = _logger.getChild(f"VfsTree")

    VfsTreeDir = VfsTreeDir
    VfsTreeDirContent = VfsTreeDirContent

    def __init__(self) -> None:
        Subscribable.__init__(self)

        self._dir_by_path: dict[str, VfsTreeDir] = {}
        self._path_dy_dir: dict[VfsTreeDir, str] = {}
        self._subdirs = SubdirsRegistry()

    def __repr__(self) -> str:
        return f"VfsTree()"

    @property
    def path(self):
        return "/"

    @property
    def tree(self) -> VfsTreeProto:
        return self

    async def child_updated(self, updates: list[TreeEventType]):
        """Notifies tree subscribers with subchild `updates`"""

        self.logger.trace(f"child_updated({updates})")

        await self.notify(updates)

    async def remove_content(
        self,
        path: str,
        item: vfs.DirContentItem,
    ):
        """Removes `item` from `path` notifying parent dir with `UpdateRemovedItems`."""
        sd = await self.get_dir(path)

        await sd._remove_from_content(item)

        await sd.child_updated(
            [TreeEventRemovedItems(sender=sd, removed_items=[item])],
        )

    async def put_content(
        self,
        content: Sequence[vfs.DirContentItem],
        path: str = "/",
        *,
        replace=False,
        notify=True,
    ):
        """Put a sequence of `vfs.DirContentItem` at `path`."""
        sd = await self.get_dir(path)

        await sd._put_content(content, replace=replace)

        if notify:
            await sd.child_updated(
                [TreeEventNewItems(sender=sd, new_items=list(content))],
            )

    async def update_content(
        self,
        content: Mapping[str, vfs.DirContentItem],
        path: str = "/",
        notify=True,
    ):
        """Put a sequence of `vfs.DirContentItem` at `path`."""
        sd = await self.get_dir(path)

        await sd._update_content(content)

        if notify:
            await sd.child_updated(
                [
                    TreeEventUpdatedItems(
                        sender=sd,
                        updated_items=map_keys(
                            lambda name: util.path.path_join(path, name), content
                        ),
                    )
                ],
            )

    async def remove_dir(
        self,
        path: str,
        notify=True,
    ):
        """Removes a dir stored at `path` notifying parent dir with
        `UpdateRemovedDirs`."""

        if path == "/":
            raise VfsTreeError(f"Cannot remove root folder.")

        self.logger.debug(f"Removing {path}")

        thedir = await self.get_dir(path)
        subdirs = await self.get_subdirs(path, recursive=True)

        # parent_dir, dir_name = vfs.split_path(path, addslash=True)
        parent = await self.get_parent(path)

        for sd in subdirs:
            del self._dir_by_path[sd.path]
            del self._path_dy_dir[sd]

        del self._dir_by_path[path]
        del self._path_dy_dir[thedir]

        self._subdirs.remove_path(path)

        if notify:
            await parent.child_updated(
                # parent,  # type: ignore
                [TreeEventRemovedDirs(sender=parent, removed_dirs=[path])],
            )

    async def create_dir(self, path: str) -> VfsTreeDir:
        """Creates a subdir at `path`. Notifies parent dir with `UpdateNewDirs`
        and returns created `VfsTreeDir`"""
        return await self.put_dir(self.VfsTreeDir(self, path))

    async def put_dir(
        self,
        d: VfsTreeDir,
        notify=True,
    ) -> VfsTreeDir:
        """Put `VfsTreeDir`. May be used instead of `create_dir` method."""
        path = util.path.norm_path(d.path, addslash=True)
        # parent_dir, dir_name = vfs.split_path(path, addslash=True)

        if path in self._dir_by_path:
            self._dir_by_path[path] = d
            self._path_dy_dir[d] = path
            return self._dir_by_path[path]

        self._dir_by_path[path] = d
        self._path_dy_dir[d] = path
        self._subdirs.add_path(path)

        if path != "/":
            parent = await self.get_parent(path)

            if parent.path not in self._dir_by_path:
                await self.create_dir(parent.path)

            if notify:
                await parent.child_updated(
                    # parent,  # type: ignore
                    [TreeEventNewDirs(sender=parent, new_dirs=[path])],
                )

        return self._dir_by_path[path]

    async def get_parents(self, path_or_dir: str | VfsTreeDir) -> list[VfsTreeDir]:
        """Returns a list of parents of `path_or_dir` with first element being
        `VfsTree`"""

        if path_or_dir == "/":
            return []

        if isinstance(path_or_dir, str):
            path = path_or_dir
            thedir = await self.get_dir(path_or_dir)
        else:
            path = path_or_dir.path
            thedir = path_or_dir

        parent = await self.get_parent(path)
        result = [parent]

        while parent != self:
            parent = await self.get_parent(parent.path)
            result.append(parent)

        return result

    async def exists(self, dir_or_path: VfsTreeDir | str):
        return (
            dir_or_path.path if isinstance(dir_or_path, VfsTreeDir) else dir_or_path
        ) in self._dir_by_path

    async def get_parent(self, path: str) -> VfsTreeDir:
        """Returns parent `VfsTreeDir` for dir at `path`. Returns `VfsTree` for
        `path == '/'`"""

        if path == "/":
            raise VfsTreeError(f"Cannot get parent for /")

        parent_dir, dir_name = util.path.split_path(path, addslash=True)

        return await self.get_dir(parent_dir)

    async def get_dir_content_items(self, subpath: str) -> list[vfs.DirContentItem]:
        """Returns a list of `vfs.DirContentItem` stored at `path`"""
        sd = await self.get_dir(subpath)
        return await sd._get_dir_content_items()

    async def get_dir(self, path: str) -> "VfsTreeDir":
        """Returns `VfsTreeDir` stored at `path`"""
        if path not in self._dir_by_path:
            raise VfsTreeNotFoundError(f"Missing directory {path}", path=path)

        return self._dir_by_path[path]

    async def get_subdirs(self, path: str, *, recursive=False) -> list[VfsTreeDir]:
        """Returns a list of `VfsTreeDir` which are subdirs of dir stored at
        `path`. If `recursive` flag is set all the nested subdirs are included."""
        res = []

        subdirs = self._subdirs.get_subdirs(path, recursive)

        for s in subdirs:
            res.append(self._dir_by_path[s])

        return res

    async def get_dir_content(self, path: str = "/") -> VfsTreeDirContent:
        """Returns `VfsTreeDirContent`. Interface used by FileSystemOperations"""
        return self.VfsTreeDirContent(self, path)

    async def _get_dir_content(self, path: str) -> vfs.DirContentProto:
        """Method used by `VfsTreeDirContent` to construct `vfs.DirContentProto`"""
        d = await self.get_dir(path)

        vfs_items, subdirs = (
            await d.get_dir_content_items(),
            await d.get_subdirs(),
        )

        content = [
            *vfs_items,
            *[
                vfs.vdir(
                    sd.name,
                    await self.get_dir_content(sd.path),
                )
                for sd in subdirs
            ],
        ]

        dc: vfs.DirContentProto = vfs.dir_content(*content)

        for w in d._wrappers:
            dc = await w.wrap_dir_content(dc)

        return dc


TreeListener = SubscribableListener[TreeEventType]
