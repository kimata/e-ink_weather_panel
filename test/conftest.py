#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        "record_video_dir": "test/evidence/{test_name}".format(
            test_name=request.node.name
        ),
        "record_video_size": {"width": 2400, "height": 1600},
    }
