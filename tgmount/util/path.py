""" 
assert norm_and_parse_path("/") == ["/"]
assert norm_and_parse_path("/a") == ["/", "a"]
assert norm_and_parse_path("a") == ["a"]
assert norm_and_parse_path("a/") == ["a"]
assert norm_and_parse_path("/a/") == ["/", "a"]
assert norm_and_parse_path("/a/b") == ["/", "a", "b"]
assert norm_and_parse_path("a/b") == ["a", "b"]
assert norm_and_parse_path("/a/b/") == ["/", "a", "b"]
assert norm_and_parse_path("/a/b/c") == ["/", "a", "b", "c"]
"""


import os
from typing import Iterable, Mapping


def path_join(*paths: str):
    return os.path.join("/", *[path_remove_slash(p) for p in paths])


def path_remove_slash(path: str):
    if path.startswith("/"):
        return path[1:]

    return path


from functools import lru_cache


@lru_cache
def norm_path(p: str, addslash=False):
    if p == "":
        p = "/"

    p = os.path.normpath(p)

    if p.startswith("/") or not addslash:
        return p

    return "/" + p


def parent_path(p: str):
    return os.path.dirname(p)


def norm_and_parse_path(p: str, noslash=False):
    p = os.path.normpath(p)
    dirs = p.split(os.sep)
    if dirs[0] == "":
        dirs[0] = "/"
    if dirs[0] != "/":
        dirs = ["/", *dirs]
    if dirs[-1] == "":
        del dirs[-1]

    if p.startswith("/") and not noslash:
        return dirs

    return dirs[1:]


napp = norm_and_parse_path


def nappb(path: str, encoding: str = "utf-8", noslash=False) -> list[bytes]:
    lpath = norm_and_parse_path(path, noslash)

    return [p.encode(encoding) for p in lpath]


@lru_cache
def split_path(path: str, addslash=False):
    """Splits path into parent and child normalizing parent path optionally adding leading slash"""
    head, tail = os.path.split(path)

    return norm_path(head, addslash), tail


def paths_to_tree(paths: Iterable[str]):
    _paths = map(lambda p: norm_and_parse_path(p, True), paths)

    return _paths_to_tree(_paths)


from .func import fst, group_by0


def _paths_to_tree(paths: Iterable[list[str]]):
    res = {}
    if paths == []:
        return {}

    for dir_name, children in group_by0(fst, filter(len, paths)).items():
        res[dir_name] = _paths_to_tree([kid[1:] for kid in children])

    return res


PathsTree = Mapping[str, "PathsTree"]


def walk_paths_tree(tree: PathsTree, path: str = "/"):
    for k, v in tree.items():
        yield path_join(path, k)
        yield from walk_paths_tree(v, path_join(path, k))
