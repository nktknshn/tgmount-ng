# import dataclasses
# from typing import Any
# import pytest
# import yaml
# import os
# from pprint import pprint
# from tgmount.config import *
# from tgmount.config import root, MessageSource
# from tgmount.config.config_ng import ConfigReader, ConfigReaderContext

# from .fixtures import config_from_file


# def test_message_source():
#     ms = MessageSource.from_mapping(
#         {
#             "entity": "abcd",
#             "offset_date": "21/10/2023 11:00",
#             "filter": "filter",
#             "limit": 1000,
#             "min_id": 1,
#             "max_id": 1,
#             "reply_to": 1,
#             "wait_time": 0.01,
#         }
#     )

#     assert ms.offset_date == datetime.datetime(2023, 10, 21, 11, 0)
#     assert ms.filter == "filter"
#     assert ms.reverse is False
#     assert ms.wait_time == 0.01


# def test_config_reader():
#     reader = ConfigReader()

#     with pytest.raises(ConfigError):
#         reader.read_config({})

#     with pytest.raises(ConfigError):
#         reader.read_config({"client": 1})

#     with pytest.raises(ConfigError):
#         reader.read_config({"client": {}})

#     with pytest.raises(ConfigError):
#         reader.read_config({"client": {"session": 1}})

#     with pytest.raises(ConfigError):
#         reader.read_config(
#             {
#                 "client": {
#                     "session": "1",
#                     "api_id": 123,
#                     "api_hash": "123",
#                     "request_size": "aa",
#                 }
#             }
#         )

#     with pytest.raises(ConfigError):
#         reader.read_config(
#             {
#                 "client": {
#                     "session": "1",
#                     "api_id": 123,
#                     "api_hash": "123",
#                 },
#                 "message_sources": {"source1": {"a": 1}},
#             }
#         )

#     # reader.read_config(
#     #     {
#     #         "client": {
#     #             "session": "1",
#     #             "api_id": 123,
#     #             "api_hash": "123",
#     #         },
#     #         "message_sources": {"source1": {"entity": 123}},
#     #         "root": {"other": {"folder": {"filter": ["123", 1]}}},
#     #     }
#     # )

#     cfg = reader.read_root_config_dir(
#         {
#             "source1": {"filter": [1, 2, 3], "source": "1"},
#         }
#     )

#     # assert cfg.other_keys["source1"].source is not None
#     print(cfg.other_keys["source1"])
