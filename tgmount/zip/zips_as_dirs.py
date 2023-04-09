from dataclasses import dataclass
from typing import Iterable, Optional

from tgmount import tglog
from tgmount import vfs
from tgmount.vfs.types.dir import DirContentItem
from tgmount.zip.zip_dir_factory import DirContentZipFactory
from .util import get_uniq_name


@dataclass
class ZipsAsDirsHandle:
    items: list[vfs.DirContentItem]
