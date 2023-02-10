import os
from tgmount.util.path import norm_path, paths_to_tree, walk_paths_tree
from tgmount.vfs.util import norm_and_parse_path
from tgmount import vfs
from tgmount.zip.util import group_dirs_into_tree


def test_vfs_split_path():
    print(vfs.split_path("/"))
    # assert vfs.split_path("/") == "/", ""


def test_parse_path():
    assert norm_and_parse_path("/") == ["/"]
    assert norm_and_parse_path("/a") == ["/", "a"]
    assert norm_and_parse_path("a") == ["a"]
    assert norm_and_parse_path("a/") == ["a"]
    assert norm_and_parse_path("/a/") == ["/", "a"]
    assert norm_and_parse_path("/a/b") == ["/", "a", "b"]
    assert norm_and_parse_path("a/b") == ["a", "b"]
    assert norm_and_parse_path("/a/b/") == ["/", "a", "b"]
    assert norm_and_parse_path("/a/b/c") == ["/", "a", "b", "c"]

    assert norm_and_parse_path("/a/b/c", True) == ["a", "b", "c"]
    assert norm_and_parse_path("a/b/c", True) == ["a", "b", "c"]
    assert norm_and_parse_path("/", True) == []


# should normalize
def test_parse_path_norm():
    assert norm_and_parse_path("/.") == ["/"]
    assert norm_and_parse_path("/a/..") == ["/"]
    assert norm_and_parse_path("a/../a") == ["a"]
    assert norm_and_parse_path("./a/./../a/") == ["a"]


def test_paths_to_tree():
    tree = paths_to_tree(["/a/b/c/d/e", "a/b/g/f", "d/h/i/k", "a", "k"])
    assert tree == {
        "a": {
            "b": {"c": {"d": {"e": {}}}, "g": {"f": {}}},
        },
        "d": {"h": {"i": {"k": {}}}},
        "k": {},
    }

    # print(list(walk_paths_tree(tree)))
    # print(norm_path("/a/a/"))
