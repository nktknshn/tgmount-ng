from tgmount.vfs.vfs_tree_types import VfsTreeError, VfsTreeNotFoundError
from tgmount import util


class SubdirsRegistry:
    """Stores mapping path -> list[path]"""

    def __init__(self) -> None:
        self._subdirs_by_path: dict[str, list[str]] = {}

    def add_path(self, path: str):
        """"""

        if path in self._subdirs_by_path:
            raise VfsTreeError(f"SubdirsRegistry: {path} is already in registry")

        self._subdirs_by_path[path] = []

        parent, name = util.path.split_path(path)

        if name == "":
            return

        if parent not in self._subdirs_by_path:
            raise VfsTreeNotFoundError(
                f"SubdirsRegistry: error putting {path}. Missing parent {parent} "
                f"in registry",
                path=parent,
            )

        self._subdirs_by_path[parent].append(path)

    def remove_path(self, path: str):
        parent_path = util.path.parent_path(path)

        self._subdirs_by_path[parent_path].remove(path)

        subdirs = self.get_subdirs(path, recursive=True)

        for sd in subdirs:
            del self._subdirs_by_path[sd]

        del self._subdirs_by_path[path]

    def get_subdirs(self, path: str, recursive=False) -> list[str]:
        subs = self._subdirs_by_path.get(path)

        if subs is None:
            raise VfsTreeNotFoundError(
                f"SubdirsRegistry: Missing {path} in registry", path=path
            )

        # subs = subs[:]
        subssubs = []

        if recursive:
            for s in subs:
                subssubs.extend(self.get_subdirs(s, recursive=True))

        return [*subs, *subssubs]
