from pprint import pprint

import pytest

from tests.helpers.config import create_config
from tests.helpers.mocked.mocked_storage import MockedTelegramStorage
from tests.integrational.integrational_test import MockedTgmountBuilderBase
from tgmount.tgmount.validator import ConfigValidator

builder = MockedTgmountBuilderBase(MockedTelegramStorage())


@pytest.mark.asyncio
async def test_validator():
    cfg = create_config(
        root={
            # "filter": "NonExisting"
            "filter": {"Not": {"Union": ["NonExisting"]}},
        },
    )

    validator = ConfigValidator(builder)
    with pytest.raises(Exception):
        await validator.verify_config(cfg)

    # pprint(cfg)
