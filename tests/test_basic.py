#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import pytest
import re
import datetime

sys.path.append(str(pathlib.Path(__file__).parent.parent / "app"))
sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))
from config import load_config

from webapp import create_app

CONFIG_FILE = "config.example.yaml"
CONFIG_SMALL_FILE = "config.example.yaml"


@pytest.fixture(scope="session")
def app():
    os.environ["TEST"] = "true"
    os.environ["WERKZEUG_RUN_MAIN"] = "true"

    app = create_app(CONFIG_FILE, CONFIG_SMALL_FILE, dummy_mode=True)

    yield app


@pytest.fixture()
def client(app):

    test_client = app.test_client()

    yield test_client

    test_client.delete()


def gen_wbgt_info():
    return {
        "current": 32,
        "daily": {
            "today": list(range(18, 34, 2)),
            "tommorow": list(range(18, 34, 2)),
        },
    }


def gen_sensor_data(valid=True):
    return {
        "value": [1, 10, 20],
        "time": [
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=-3),
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=-2),
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=-1),
        ],
        "valid": valid,
    }


######################################################################
def test_weather_panel():
    import weather_panel

    weather_panel.create_weather_panel(load_config(CONFIG_FILE), False)

    # NOTE: エラーが発生しなければ OK


def test_weather_panel_dummy(mocker):
    import weather_panel
    import copy

    wather_info_day = [
        {
            "hour": 1,
            "weather": {
                "text": "曇り",
                "icon_url": "https://s.yimg.jp/images/weather/general/next/pinpoint/size80/31_day.png",
            },
            "temp": 0,
            "humi": 0,
            "precip": 0,
            "wind": {"dir": "北", "speed": 0},
        }
        for i in range(8)
    ]
    precip_list = [0, 1, 2, 3, 10, 20]
    speed_list = [0, 1, 2, 3, 4, 5]

    for i in range(2, 8):
        wather_info_day[i]["precip"] = precip_list[i - 2]
        wather_info_day[i]["wind"]["speed"] = speed_list[i - 2]

    weather_info = {
        "today": wather_info_day,
        "tommorow": copy.deepcopy(wather_info_day),
    }
    weather_info["tommorow"][3]["wind"]["dir"] = "静穏"
    clothing_info = {"today": 0, "tommorow": 50}
    wbgt_info = {"daily": {"today": list(range(9)), "tommorow": None}}

    mocker.patch("weather_panel.get_weather_yahoo", return_value=weather_info)
    mocker.patch("weather_panel.get_clothing_yahoo", return_value=clothing_info)
    mocker.patch("weather_panel.get_wbgt", return_value=wbgt_info)

    weather_panel.create_weather_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_wbgt_panel():
    import wbgt_panel

    wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


def test_wbgt_panel_var(mocker):
    import wbgt_panel

    wbgt_info = gen_wbgt_info()
    for i in range(20, 34, 2):
        wbgt_info["current"] = i
        mocker.patch("wbgt_panel.get_wbgt", return_value=wbgt_info)
        wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OKw


def test_wbgt_panel_error_1(mocker):
    import wbgt_panel

    mocker.patch("weather_data.fetch_page", side_effect=RuntimeError())
    wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


def test_wbgt_panel_error_2(mocker):
    import wbgt_panel

    mocker.patch("lxml.html.HtmlElement.xpath", return_value=[])

    wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


def test_wbgt_panel_error_3(mocker):
    import wbgt_panel

    mock = mocker.patch("weather_data.datetime")
    mock.date.day.return_value = 100

    wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_time_panel():
    import time_panel

    time_panel.create_time_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_create_power_graph(mocker):
    import power_graph

    mocker.patch("power_graph.fetch_data", return_value=gen_sensor_data())

    power_graph.create_power_graph(load_config(CONFIG_FILE))

    os.environ["DUMMY_MODE"] = "true"
    power_graph.create_power_graph(load_config(CONFIG_FILE))
    del os.environ["DUMMY_MODE"]

    # NOTE: エラーが発生しなければ OK


def test_create_power_graph_invalid(mocker):
    import power_graph

    mocker.patch("power_graph.fetch_data", return_value=gen_sensor_data())
    power_graph.create_power_graph(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_create_sensor_graph(freezer, mocker):
    import sensor_graph

    mocker.patch("sensor_graph.fetch_data", return_value=gen_sensor_data())

    freezer.move_to(datetime.datetime.now().replace(hour=12))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    freezer.move_to(datetime.datetime.now().replace(hour=20))
    os.environ["DUMMY_MODE"] = "true"
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))
    del os.environ["DUMMY_MODE"]

    # NOTE: エラーが発生しなければ OK


def test_create_sensor_graph_invalid(mocker):
    import sensor_graph
    import inspect

    def dummy_data(db_config, measure, hostname, field, start, stop, last=False):
        dummy_data.i += 1
        if (dummy_data.i % 4 == 0) or (
            inspect.stack()[4].function == "get_aircon_power"
        ):
            return gen_sensor_data(False)
        else:
            return gen_sensor_data()

    dummy_data.i = 0

    mocker.patch("sensor_graph.fetch_data", side_effect=dummy_data)
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_create_rain_cloud_panel():
    import rain_cloud_panel

    rain_cloud_panel.WINDOW_SIZE_CACHE.unlink(missing_ok=True)
    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE), True)

    # NOTE: エラーが発生しなければ OK


def test_create_rain_cloud_panel_cache(mocker):
    import rain_cloud_panel

    month_ago = datetime.datetime.now() + datetime.timedelta(days=-1)
    month_ago_epoch = month_ago.timestamp()
    rain_cloud_panel.WINDOW_SIZE_CACHE.touch()
    os.utime(
        str(rain_cloud_panel.WINDOW_SIZE_CACHE), (month_ago_epoch, month_ago_epoch)
    )

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    mocker.patch("pickle.load", side_effect=RuntimeError())
    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_create_rain_cloud_panel_error(mocker):
    import rain_cloud_panel
    import slack_sdk

    # NOTE: ついでに Slack 通知をエラーにする
    mocker.patch(
        "slack_sdk.web.client.WebClient.chat_postMessage",
        side_effect=slack_sdk.errors.SlackClientError(),
    )
    mocker.patch("rain_cloud_panel.fetch_cloud_image", side_effect=RuntimeError())

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_create_image_test(mocker):
    import create_image

    create_image.create_image(CONFIG_FILE, test_mode=True)

    # NOTE: エラーが発生しなければ OK


def test_create_image_error(mocker):
    import slack_sdk
    import create_image
    import notify_slack

    notify_slack.clear_interval()

    mocker.patch("sensor_data.fetch_data", return_value=gen_sensor_data())

    create_image.create_image(CONFIG_FILE, small_mode=True, dummy_mode=True)

    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())
    mocker.patch(
        "slack_sdk.web.client.WebClient.chat_postMessage",
        side_effect=slack_sdk.errors.SlackClientError(),
    )

    create_image.create_image(CONFIG_FILE)

    # NOTE: エラーが発生しなければ OK


######################################################################
def test_redirect(client):
    response = client.get("/")
    assert response.status_code == 302
    assert re.search(r"/weather_panel/$", response.location)


def test_index(client):
    response = client.get("/weather_panel/")
    assert response.status_code == 200
    assert "気象パネル画像" in response.data.decode("utf-8")

    response = client.get("/weather_panel/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200


def test_index_with_other_status(client, mocker):
    mocker.patch(
        "flask.wrappers.Response.status_code",
        return_value=301,
        new_callable=mocker.PropertyMock,
    )

    response = client.get("/weather_panel/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 301


def test_api_run(client, mocker):
    import inspect
    import PIL.Image
    import io

    def dummy_time():
        dummy_time.i += 1
        if (dummy_time.i == 1) or (inspect.stack()[4].function == "generate_image"):
            return (datetime.datetime.now() + datetime.timedelta(days=-1)).timestamp()
        else:
            return datetime.datetime.now().timestamp()

    dummy_time.i = 0

    mocker.patch("time.time", side_effect=dummy_time)

    # NOTE: 1回目
    response = client.get(
        "/weather_panel/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]
    response = client.post("/weather_panel/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    # NOTE: 2回目
    response = client.get(
        "/weather_panel/api/run",
        query_string={
            "mode": "small",
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]

    response = client.post("/weather_panel/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    # NOTE: 3回目
    response = client.get(
        "/weather_panel/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]

    response = client.post("/weather_panel/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    response = client.post("/weather_panel/api/image", data={"token": token})
    assert response.status_code == 200
    # NOTE: サイズが適度にあり，PNG として解釈できれば OK とする
    assert len(response.data) > 1024
    assert PIL.Image.open(io.BytesIO(response.data)).size == (3200, 1800)


def test_api_run_error(client, mocker):
    mocker.patch("generator.generate_image", side_effect=RuntimeError())

    response = client.get(
        "/weather_panel/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    response = client.post("/weather_panel/api/log", data={"token": "TEST"})
    assert response.status_code == 200

    response = client.post("/weather_panel/api/image", data={"token": "TEST"})
    assert response.status_code == 200
