from tgmount import vfs
from .readable import FileSystemOperationsBase
from .writable import FileSystemOperationsWritable
from .update import FileSystemOperationsUpdatable


class FileSystemOperations(
    FileSystemOperationsWritable,
    FileSystemOperationsUpdatable,
):
    def __init__(self, root: vfs.DirContentProto | None):
        super().__init__(root)
