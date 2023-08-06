#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NOTE: 先に pandas を import しないと，下記のエラーがでる
# TypeError: type 'pandas._libs.tslibs.base.ABCTimestamp' is not dynamically allocated
# but its base type 'FakeDatetime' is dynamically...
import pandas  # noqa: F401
import pytest


def pytest_addoption(parser):
    parser.addoption("--host", default="127.0.0.1")
    parser.addoption("--port", default="5000")


@pytest.fixture
def host(request):
    return request.config.getoption("--host")


@pytest.fixture
def port(request):
    return request.config.getoption("--port")


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args, request):
    return {
        **browser_context_args,
        "record_video_dir": "tests/evidence/{test_name}".format(test_name=request.node.name),
        "record_video_size": {"width": 2400, "height": 1600},
    }
