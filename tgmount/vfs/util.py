import os
from collections.abc import Callable
from typing import List

from tgmount.util.path import *


def lazy_list_from_thunk(content_thunk: Callable[[], List]):
    content = []

    def _inner():
        if not content:
            content.extend(content_thunk())
        return content

    async def f(off):
        return _inner()[off:]

    return f
