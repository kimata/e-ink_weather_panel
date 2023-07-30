#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import pathlib
import pytest
import re
import datetime
from unittest import mock

sys.path.append(str(pathlib.Path(__file__).parent.parent / "app"))
sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

from config import load_config
from webapp import create_app

CONFIG_FILE = "config.example.yaml"
CONFIG_SMALL_FILE = "config-small.example.yaml"


@pytest.fixture(scope="session", autouse=True)
def env_mock():
    with mock.patch.dict(
        "os.environ",
        {
            "TEST": "true",
            "NO_COLORED_LOGS": "true",
        },
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session", autouse=True)
def slack_mock():
    with mock.patch(
        "notify_slack.slack_sdk.web.client.WebClient.chat_postMessage",
        retunr_value=True,
    ) as fixture:
        yield fixture


@pytest.fixture(scope="session")
def app():
    with mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        app = create_app(CONFIG_FILE, CONFIG_SMALL_FILE, dummy_mode=True)

        yield app


@pytest.fixture(scope="function", autouse=True)
def clear():
    import notify_slack

    config = load_config(CONFIG_FILE)

    pathlib.Path(config["LIVENESS"]["FILE"]).unlink(missing_ok=True)

    notify_slack.clear_interval()
    notify_slack.clear_hist()


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


def mock_sensor_fetch_data(mocker):
    def fetch_data_mock(
        db_config,
        measure,
        hostname,
        field,
        start="-30h",
        stop="now()",
        every_min=1,
        window_min=3,
        create_empty=True,
        last=False,
    ):
        if field in fetch_data_mock.count:
            fetch_data_mock.count[field] += 1
        else:
            fetch_data_mock.count[field] = 1

        count = fetch_data_mock.count[field]

        if field == "temp":
            return gen_sensor_data([30, 15, 0])
        elif field == "power":
            if count % 3 == 1:
                return gen_sensor_data([1500, 750, 0])
            elif count % 3 == 2:
                return gen_sensor_data([20, 10, 0])
            else:
                return gen_sensor_data([1000, 500, 0], False)
        elif field == "lux":
            if count % 3 == 0:
                return gen_sensor_data([0, 250, 500])
            elif count % 3 == 1:
                return gen_sensor_data([0, 4, 8])
            else:
                return gen_sensor_data([0, 25, 500], False)
        elif field == "solar_rad":
            return gen_sensor_data([300, 150, 0])
        else:
            return gen_sensor_data([30, 15, 0])

    fetch_data_mock.count = {}

    mocker.patch("sensor_graph.fetch_data", side_effect=fetch_data_mock)
    mocker.patch("power_graph.fetch_data", side_effect=fetch_data_mock)


def gen_sensor_data(value=[30, 34, 25], valid=True):
    sensor_data = {
        "value": value,
        "time": [],
        "valid": valid,
    }

    for i in range(len(value)):
        sensor_data["time"].append(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=i - len(value))
        )

    return sensor_data


def check_notify_slack(message, index=-1):
    import notify_slack

    if message is None:
        assert notify_slack.get_hist() == [], "正常なはずなのに，エラー通知がされています．"
    else:
        assert (
            notify_slack.get_hist()[index].find(message) != -1
        ), "「{message}」が Slack で通知されていません．".format(message=message)


######################################################################
def test_weather_panel():
    import weather_panel

    weather_panel.create_weather_panel(load_config(CONFIG_FILE), False)

    check_notify_slack(None)


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

    check_notify_slack(None)


######################################################################
def test_wbgt_panel():
    import wbgt_panel

    wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_wbgt_panel_var(mocker):
    import wbgt_panel

    wbgt_info = gen_wbgt_info()
    for i in range(20, 34, 2):
        wbgt_info["current"] = i
        mocker.patch("wbgt_panel.get_wbgt", return_value=wbgt_info)
        wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_wbgt_panel_error_1(mocker):
    import wbgt_panel

    mocker.patch("weather_data.fetch_page", side_effect=RuntimeError())
    ret = wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    assert len(ret) == 3
    assert "Traceback" in ret[2]


def test_wbgt_panel_error_2(mocker):
    import wbgt_panel

    mocker.patch("lxml.html.HtmlElement.xpath", return_value=[])

    ret = wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    assert len(ret) == 3
    assert "Traceback" in ret[2]


def test_wbgt_panel_error_3(mocker):
    import wbgt_panel

    mock = mocker.patch("weather_data.datetime")
    mock.date.day.return_value = 100

    ret = wbgt_panel.create_wbgt_panel(load_config(CONFIG_FILE))

    assert len(ret) == 3
    assert "Traceback" in ret[2]


######################################################################
def test_time_panel():
    import time_panel

    time_panel.create_time_panel(load_config(CONFIG_FILE))

    check_notify_slack(None)


######################################################################
def test_create_power_graph(mocker):
    import power_graph

    mock_sensor_fetch_data(mocker)

    power_graph.create_power_graph(load_config(CONFIG_FILE))

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    power_graph.create_power_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_create_power_graph_invalid(mocker):
    import power_graph

    mocker.patch(
        "power_graph.fetch_data", return_value=gen_sensor_data([1000, 500, 0], False)
    )

    power_graph.create_power_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


######################################################################
def test_create_sensor_graph_1(freezer, mocker):
    import sensor_graph

    mock_sensor_fetch_data(mocker)

    freezer.move_to(datetime.datetime.now().replace(hour=12))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    freezer.move_to(datetime.datetime.now().replace(hour=20))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_create_sensor_graph_2(freezer, mocker):
    import sensor_graph

    def value_mock():
        value_mock.i += 1
        if value_mock.i == 1:
            return None
        else:
            return 1

    value_mock.i = 0

    table_entry_mock = mocker.MagicMock()
    record_mock = mocker.MagicMock()
    query_api_mock = mocker.MagicMock()
    mocker.patch.object(
        record_mock,
        "get_value",
        side_effect=value_mock,
    )
    mocker.patch.object(
        record_mock,
        "get_time",
        return_value=datetime.datetime.now(datetime.timezone.utc),
    )
    table_entry_mock.__iter__.return_value = [record_mock for _ in range(10)]
    type(table_entry_mock).records = table_entry_mock
    query_api_mock.query.return_value = [table_entry_mock]
    mocker.patch(
        "influxdb_client.InfluxDBClient.query_api",
        return_value=query_api_mock,
    )

    freezer.move_to(datetime.datetime.now().replace(hour=12))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_create_sensor_graph_dummy(freezer, mocker):
    import sensor_graph

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    mock_sensor_fetch_data(mocker)

    freezer.move_to(datetime.datetime.now().replace(hour=12))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    freezer.move_to(datetime.datetime.now().replace(hour=20))
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_create_sensor_graph_invalid(mocker):
    import sensor_graph
    import inspect

    def dummy_data(db_config, measure, hostname, field, start, stop, last=False):
        dummy_data.i += 1
        if (dummy_data.i % 4 == 0) or (
            inspect.stack()[4].function == "get_aircon_power"
        ):
            return gen_sensor_data(valid=False)
        else:
            return gen_sensor_data()

    dummy_data.i = 0

    mocker.patch("sensor_graph.fetch_data", side_effect=dummy_data)
    sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    check_notify_slack(None)


def test_create_sensor_graph_influx_error(mocker):
    import sensor_graph

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    ret = sensor_graph.create_sensor_graph(load_config(CONFIG_FILE))

    assert len(ret) == 3
    assert "Traceback" in ret[2]


######################################################################
def test_create_rain_cloud_panel(mocker):
    import rain_cloud_panel

    rain_cloud_panel.WINDOW_SIZE_CACHE.unlink(missing_ok=True)
    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    rain_cloud_panel.create_rain_cloud_panel(
        load_config(CONFIG_SMALL_FILE), is_side_by_side=False
    )

    check_notify_slack(None)


def test_create_rain_cloud_panel_cache_and_error(mocker):
    from selenium_util import xpath_exists
    import rain_cloud_panel

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    month_ago = datetime.datetime.now() + datetime.timedelta(days=-1)
    month_ago_epoch = month_ago.timestamp()
    rain_cloud_panel.WINDOW_SIZE_CACHE.touch()
    os.utime(
        str(rain_cloud_panel.WINDOW_SIZE_CACHE), (month_ago_epoch, month_ago_epoch)
    )

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    mocker.patch("pickle.load", side_effect=RuntimeError())
    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    check_notify_slack("Traceback")


def test_create_rain_cloud_panel_selenium_error(mocker):
    from selenium_util import create_driver_impl
    import rain_cloud_panel

    # NOTE: 一回だけエラーにする
    def create_driver_impl_mock(profile_name, data_path):
        create_driver_impl_mock.i += 1
        if create_driver_impl_mock.i == 1:
            raise RuntimeError()
        else:
            return create_driver_impl(profile_name, data_path)

    create_driver_impl_mock.i = 0

    mocker.patch(
        "selenium_util.create_driver_impl", side_effect=create_driver_impl_mock
    )

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_SMALL_FILE))

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので，None になる
    check_notify_slack(None)


def test_create_rain_cloud_panel_xpath_error(mocker):
    from selenium_util import xpath_exists
    import rain_cloud_panel

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_SMALL_FILE))

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので，None になる
    check_notify_slack(None)


######################################################################
def test_create_image(mocker):
    import create_image

    create_image.create_image(CONFIG_FILE, test_mode=True)
    create_image.create_image(CONFIG_FILE)

    check_notify_slack(None)


def test_create_image_small(mocker):
    import create_image

    create_image.create_image(CONFIG_SMALL_FILE, test_mode=False)

    check_notify_slack(None)


def test_create_image_error(mocker):
    import create_image

    mock_sensor_fetch_data(mocker)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    create_image.create_image(CONFIG_FILE, small_mode=True, dummy_mode=True)

    # NOTE: 2回目
    create_image.create_image(CONFIG_SMALL_FILE)

    check_notify_slack("Traceback")


def test_create_image_influx_error(mocker):
    import create_image

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    create_image.create_image(CONFIG_FILE, small_mode=False, dummy_mode=True)

    # NOTE: sensor_graph と power_graph のそれぞれでエラーが発生
    check_notify_slack("Traceback", index=-1)
    check_notify_slack("Traceback", index=-2)


def test_slack_error(mocker):
    import slack_sdk
    import create_image

    mock_sensor_fetch_data(mocker)

    def webclient_mock(self, token):
        raise slack_sdk.errors.SlackClientError()

    mocker.patch.object(slack_sdk.web.client.WebClient, "__init__", webclient_mock)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    create_image.create_image(CONFIG_FILE, small_mode=True, dummy_mode=True)

    check_notify_slack("Traceback")


def test_slack_error_with_image(mocker):
    import rain_cloud_panel
    from rain_cloud_panel import fetch_cloud_image

    def fetch_cloud_image_mock(driver, url, width, height, is_future=False):
        fetch_cloud_image_mock.i += 1
        if fetch_cloud_image_mock.i == 1:
            return fetch_cloud_image(driver, url, width, height, is_future)
        else:
            raise RuntimeError()

    fetch_cloud_image_mock.i = 0

    mocker.patch(
        "rain_cloud_panel.fetch_cloud_image", side_effect=fetch_cloud_image_mock
    )

    rain_cloud_panel.create_rain_cloud_panel(load_config(CONFIG_FILE))

    check_notify_slack("Traceback")


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
    import gzip

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

    response = client.post(
        "/weather_panel/api/image",
        headers={"Accept-Encoding": "gzip"},
        data={"token": token},
    )
    assert response.status_code == 200
    image_data = gzip.decompress(response.data)
    # NOTE: サイズが適度にあり，PNG として解釈できれば OK とする
    assert len(image_data) > 1024
    assert PIL.Image.open(io.BytesIO(image_data)).size == (3200, 1800)


def test_api_run_small(client, mocker):
    import inspect
    import json

    CALLBACK = "TEST"

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
            "mode": "small",
            "callback": CALLBACK,
        },
    )
    assert response.status_code == 200

    m = re.compile(
        r"{callback}\((.*)\)".format(callback=CALLBACK), re.MULTILINE | re.DOTALL
    ).match(response.text)

    assert m is not None

    token = json.loads(m.group(1))["token"]

    response = client.post("/weather_panel/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()


def test_api_run_error(client, mocker):
    mocker.patch("generator.generate_image", side_effect=RuntimeError())

    response = client.get(
        "/weather_panel/api/run",
        query_string={"test": True, "mode": "small"},
    )
    assert response.status_code == 200

    response = client.post("/weather_panel/api/log", data={"token": "TEST"})
    assert response.status_code == 200

    response = client.post("/weather_panel/api/image", data={"token": "TEST"})
    assert response.status_code == 200


def test_api_run_normal(mocker):
    import inspect

    # NOTE: fixture の方はダミーモード固定で動かしているので，
    # ここではノーマルモードで webapp を動かしてテストする．
    mocker.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"})
    app = create_app(CONFIG_FILE, CONFIG_SMALL_FILE)
    client = app.test_client()

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
    # NOTE: ログを出し切るまで待つ．
    response.data.decode()

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
    response.data.decode()

    client.delete()


######################################################################


def test_display_image(mocker):
    import builtins
    import display_image
    from config import load_config

    ssh_client_mock = mocker.MagicMock()

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", new=ssh_client_mock)

    orig_open = builtins.open

    def open_mock(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        if file == "TEST":
            return mocker.MagicMock()
        else:
            return orig_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_config(CONFIG_SMALL_FILE)
    config["PANEL"]["UPDATE"]["INTERVAL"] = 60
    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        is_small_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    check_notify_slack(None)


def test_display_image_onetime(mocker):
    import builtins
    import display_image
    from config import load_config

    ssh_client_mock = mocker.MagicMock()

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", new=ssh_client_mock)

    orig_open = builtins.open

    def open_mock(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        if file == "TEST":
            return mocker.MagicMock()
        else:
            return orig_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )

    mocker.patch("builtins.open", side_effect=open_mock)

    display_image.display_image(
        load_config(CONFIG_FILE),
        "TEST",
        "TEST",
        CONFIG_FILE,
        is_small_mode=False,
        is_one_time=True,
    )

    check_notify_slack(None)


def test_display_image_error(mocker):
    import builtins
    import display_image
    from config import load_config

    ssh_client_mock = mocker.MagicMock()
    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=222)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", new=ssh_client_mock)
    mocker.patch("subprocess.Popen", return_value=subprocess_popen_mock)

    orig_open = builtins.open

    def open_mock(
        file,
        mode="r",
        buffering=-1,
        encoding=None,
        errors=None,
        newline=None,
        closefd=True,
        opener=None,
    ):
        if file == "TEST":
            return mocker.MagicMock()
        else:
            return orig_open(
                file, mode, buffering, encoding, errors, newline, closefd, opener
            )

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_config(CONFIG_SMALL_FILE)
    config["PANEL"]["UPDATE"]["INTERVAL"] = 60
    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        is_small_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    # NOTE: 本来，create_image の中で通知されているので，上記の胡椒注入方法では通知はされない
    check_notify_slack(None)
