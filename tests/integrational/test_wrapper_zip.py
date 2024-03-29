import logging
import os
import pytest

from pprint import pprint
from tgmount import vfs, zip as z
from tests.integrational.helpers import mdict
from tests.helpers.config import create_config
from tgmount.tgmount.vfs_tree_types import (
    TreeEventNewDirs,
    TreeEventNewItems,
    TreeEventRemovedDirs,
)
from tgmount.tgmount.wrappers.wrapper_exclude_empty_dirs import WrapperEmpty

from .fixtures import *
from .context import Context

from ..logger import logger as _logger


root_cfg1 = {
    "source": {
        "source": "source1",
        "recursive": True,
    },
    "filter": "MessageWithZip",
    "wrappers": {
        "ZipsAsDirs": {
            "skip_single_root_subfolder": False,
        }
    },
}

producer_cfg = {
    "source": {
        "source": "source1",
        "recursive": True,
    },
    # "filter": "MessageWithZip",
    "producer": {
        "UnpackedZip": {
            "skip_single_root_subfolder": False,
        }
    },
}


async def prepare_ctx(fixtures: Fixtures):
    ctx = Context.from_fixtures(fixtures)

    config = create_config(
        message_sources={"source1": "source1"},
        root=root_cfg1,
    )

    ctx.set_config(config)

    await ctx.source1.document(file=ctx.files.zip_debrecen.path)
    await ctx.source1.document(file=ctx.files.zip_bandcamp.path)

    return ctx


@pytest.mark.asyncio
async def test_simple_remove1(fixtures: Fixtures):
    """Unpacked zip archive will be removed when a message removed"""
    ctx = await prepare_ctx(fixtures)
    # ctx.debug = logging.DEBUG

    fname1 = ctx.files.zip_debrecen.basename
    fname2 = ctx.files.zip_bandcamp.basename

    zf1 = await ctx.files.zip_debrecen.zip_file()
    zf2 = await ctx.files.zip_bandcamp.zip_file()

    fls1 = z.zip_ls(zf1)
    fls2 = z.zip_ls(zf2)

    assert fls1
    assert fls2

    async def test():
        assert await ctx.listdir_set("/") == {
            f"1_{fname1}",
            f"2_{fname2}",
        }

        assert await ctx.listdir_set("/", f"1_{fname1}") == set(fls1.keys())
        assert await ctx.listdir_set("/", f"2_{fname2}") == set(fls2.keys())

        await ctx.client.delete_messages(ctx.source1.entity_id, msg_ids=[1])

        assert await ctx.listdir_set("/") == {f"2_{fname2}"}
        assert await ctx.listdir_set("/", f"2_{fname2}") == set(fls2.keys())

    await ctx.run_test(test, cfg_or_root=producer_cfg)


@pytest.mark.asyncio
async def test_simple_remove_single_folder(fixtures: Fixtures):
    ctx = await prepare_ctx(fixtures)

    fname1 = ctx.files.zip_debrecen.basename
    fname2 = ctx.files.zip_bandcamp.basename

    zf1 = await ctx.files.zip_debrecen.zip_file()
    zf2 = await ctx.files.zip_bandcamp.zip_file()

    fls1 = z.zip_ls(zf1, path=["2010_Debrecen"])
    fls2 = z.zip_ls(zf2)

    assert fls1
    assert fls2

    async def test():
        assert await ctx.listdir_set("/") == {
            f"1_2010_Debrecen",
            f"2_{fname2}",
        }

        assert await ctx.listdir_set("/", f"1_2010_Debrecen") == set(fls1.keys())
        assert await ctx.listdir_set("/", f"2_{fname2}") == set(fls2.keys())

        await ctx.client.delete_messages(ctx.source1.entity_id, msg_ids=[1])

        assert await ctx.listdir_set("/") == {
            f"2_{fname2}",
        }

    await ctx.run_test(
        test,
        cfg_or_root=mdict(producer_cfg)
        .update(
            {"skip_single_root_subfolder": True},
            at="/producer/UnpackedZip",
        )
        .get(),
    )


@pytest.mark.asyncio
async def test_simple_remove_hide_files_false(fixtures: Fixtures):
    """Both file and directory removed"""
    ctx = await prepare_ctx(fixtures)
    # ctx.debug = logging.DEBUG

    fname1 = ctx.files.zip_debrecen.basename
    fname2 = ctx.files.zip_bandcamp.basename

    async def test():
        assert await ctx.listdir_set("/") == {
            f"1_{fname1}",
            f"1_{fname1}_unzipped",
            f"2_{fname2}",
            f"2_{fname2}_unzipped",
        }

        await ctx.client.delete_messages(ctx.source1.entity_id, msg_ids=[1])

        assert await ctx.listdir_set("/") == {
            f"2_{fname2}",
            f"2_{fname2}_unzipped",
        }

    await ctx.run_test(
        test,
        cfg_or_root=mdict(producer_cfg)
        .update(
            {"hide_zip_files": False},
            at="/producer/UnpackedZip",
        )
        .get(),
    )


@pytest.mark.asyncio
async def test_simple4(fixtures: Fixtures):
    ctx = await prepare_ctx(fixtures)

    fname1 = ctx.files.zip_debrecen.basename
    fname2 = ctx.files.zip_bandcamp.basename

    async def test():
        assert await ctx.listdir_set("/") == {
            f"1_{fname1}",
            f"1_2010_Debrecen",
            f"2_{fname2}",
            f"2_{fname2}_unzipped",
        }

    await ctx.run_test(
        test,
        cfg_or_root=mdict(producer_cfg)
        .update(
            {"hide_zip_files": False, "skip_single_root_subfolder": True},
            at="/producer/UnpackedZip",
        )
        .get(),
    )


@pytest.mark.asyncio
async def test_simple_new_message(fixtures: Fixtures):
    ctx = Context.from_fixtures(fixtures)

    ctx.set_config(
        {
            "client": {"api_id": 1243, "api_hash": "abcd", "session": "tgfs"},
            "message_sources": {"source1": {"entity": "source1"}},
            "root": {
                "source": "source1",
                "filter": "MessageDownloadable",
                "producer": {
                    "UnpackedZip": {
                        "fix_id3v1": False,
                        "skip_single_root_subfolder": False,
                    }
                },
            },
        }
    )

    await ctx.source1.document(file=ctx.files.zip_atrium.path)
    zf2 = await ctx.files.zip_bandcamp.zip_file()
    fls2 = z.zip_ls(zf2)

    assert fls2

    async def test():
        assert await ctx.listdir_set(f"1_{ctx.files.zip_atrium.basename}") == {
            f"Atrium Carceri",
        }

        await ctx.client.send_file("source1", ctx.files.zip_bandcamp.path)
        assert await ctx.listdir_len("/") == 2
        assert await ctx.listdir_set(f"2_{ctx.files.zip_bandcamp.basename}") == set(
            fls2.keys()
        )

    await ctx.run_test(test)


@pytest.mark.asyncio
async def test_simple_new_message_skip_single_true(fixtures: Fixtures):
    ctx = Context.from_fixtures(fixtures)

    ctx.set_config(
        {
            "client": {"api_id": 1243, "api_hash": "abcd", "session": "tgfs"},
            "message_sources": {"source1": {"entity": "source1"}},
            "root": {
                "source": "source1",
                "filter": "MessageDownloadable",
                "producer": {
                    "UnpackedZip": {
                        "fix_id3v1": False,
                        "skip_single_root_subfolder": True,
                    }
                },
            },
        }
    )

    fls2 = z.zip_ls(await ctx.files.zip_atrium.zip_file(), ["Atrium Carceri"])
    assert fls2

    async def test():
        await ctx.client.send_file("source1", ctx.files.zip_atrium.path)
        assert await ctx.listdir_set(f"1_Atrium Carceri") == set(fls2.keys())

    await ctx.run_test(test)


@pytest.mark.asyncio
async def test_simple_new_message_hide_zip_false(fixtures: Fixtures):
    ctx = Context.from_fixtures(fixtures)

    ctx.set_config(
        {
            "client": {"api_id": 1243, "api_hash": "abcd", "session": "tgfs"},
            "message_sources": {"source1": {"entity": "source1"}},
            "root": {
                "source": "source1",
                "filter": "MessageDownloadable",
                "producer": {
                    "UnpackedZip": {
                        "hide_zip_files": False,
                        "skip_single_root_subfolder": False,
                    }
                },
            },
        }
    )

    fls2 = z.zip_ls(await ctx.files.zip_atrium.zip_file())
    assert fls2

    async def test():
        await ctx.client.send_file("source1", ctx.files.zip_atrium.path)

        assert await ctx.listdir_set("/") == {
            f"1_{ctx.files.zip_atrium.basename}",
            f"1_{ctx.files.zip_atrium.basename}_unzipped",
        }

        assert await ctx.listdir_set(
            f"1_{ctx.files.zip_atrium.basename}_unzipped"
        ) == set(fls2.keys())

    await ctx.run_test(test)


@pytest.mark.asyncio
async def test_simple_edit_message(fixtures: Fixtures):
    ctx = await prepare_ctx(fixtures)

    fname1 = ctx.files.zip_debrecen.basename
    fname2 = ctx.files.zip_bandcamp.basename
    bad_zip = ctx.files.zip_bad.basename

    await ctx.source1.document(file=ctx.files.zip_bad.path)

    [msg1, msg2, msg3] = ctx.source1.messages

    async def test():
        assert await ctx.listdir_set("/") == {
            f"1_{fname1}",
            f"1_2010_Debrecen",
            f"2_{fname2}",
            f"2_{fname2}_unzipped",
            f"3_{bad_zip}",
        }

        msg1_edit = await ctx.client.edit_message(
            msg1,
            await ctx.source1.document(
                file=ctx.files.zip_bandcamp.path, put=False, msg_id=msg1.id
            ),
        )

        assert await ctx.listdir_set("/") == {
            f"1_{fname2}",
            f"1_{fname2}_unzipped",
            f"2_{fname2}",
            f"2_{fname2}_unzipped",
            f"3_{bad_zip}",
        }

        assert "cover.jpg" in await ctx.listdir_set("/", f"1_{fname2}_unzipped")

        await ctx.client.edit_message(
            msg2,
            await ctx.source1.document(
                file=ctx.files.zip_bad.path, put=False, msg_id=msg2.id
            ),
        )

        assert await ctx.listdir_set("/") == {
            f"1_{fname2}",
            f"1_{fname2}_unzipped",
            f"2_{bad_zip}",
            f"3_{bad_zip}",
        }

        await ctx.client.edit_message(
            msg3,
            await ctx.source1.document(
                file=ctx.files.Hummingbird, put=False, msg_id=msg3.id
            ),
        )
        assert await ctx.listdir_set("/") == {
            f"1_{fname2}",
            f"1_{fname2}_unzipped",
            f"2_{bad_zip}",
            f"3_Hummingbird.jpg",
        }

        await ctx.client.edit_message(
            msg1_edit,
            await ctx.source1.document(
                file=ctx.files.zip_linux2.path,
                put=False,
                msg_id=msg1.id,
                file_name=fname2,
            ),
        )
        assert await ctx.listdir_set("/") == {
            f"1_{fname2}",
            f"1_{fname2}_unzipped",
            f"2_{bad_zip}",
            f"3_Hummingbird.jpg",
        }

        assert "Feat Liette   Gesloten Cirkel.mp3" in await ctx.listdir_set(
            "/", f"1_{fname2}_unzipped"
        )

    await ctx.run_test(
        test,
        cfg_or_root=mdict(producer_cfg)
        .update(
            {
                "hide_zip_files": False,
                "skip_single_root_subfolder": True,
            },
            at="/producer/UnpackedZip",
        )
        .get(),
    )


# @pytest.mark.asyncio
# async def test_fix_id3v1(fixtures: Fixtures):

#     ctx = await prepare_ctx(fixtures)

#     fname1 = ctx.files.zip_debrecen.basename
#     fname2 = ctx.files.zip_bandcamp.basename

#     async def test():
#         assert await ctx.listdir_set("/") == {
#             f"1_{fname1}",
#             f"1_2010_Debrecen",
#             f"2_{fname2}",
#             f"2_{fname2}_unzipped",
#         }

#     await ctx.run_test(
#         test,
#         cfg_or_root=mdict(root_cfg1)
#         .update(
#             {"hide_zip_files": False, "skip_single_root_subfolder": True},
#             at="/wrappers/ZipsAsDirs",
#         )
#         .get(),
#     )
