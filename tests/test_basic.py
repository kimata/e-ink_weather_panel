#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import os
import pathlib
import re
import sys
from unittest import mock

import pytest

sys.path.append(str(pathlib.Path(__file__).parent.parent / "app"))
sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import logging

logging.getLogger("selenium.webdriver.remote").setLevel(logging.WARN)
logging.getLogger("selenium.webdriver.common").setLevel(logging.DEBUG)

from config import load_config
from webapp import create_app

CONFIG_FILE = "config.example.yaml"
CONFIG_SMALL_FILE = "config-small.example.yaml"
EVIDENCE_DIR = pathlib.Path(__file__).parent / "evidence" / "image"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


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

    notify_slack.interval_clear()
    notify_slack.hist_clear()


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
            return gen_sensor_data([30, 20, 15, 0])
        elif field == "power":
            if count % 3 == 1:
                return gen_sensor_data([1500, 500, 750, 0])
            elif count % 3 == 2:
                return gen_sensor_data([20, 15, 10, 0])
            else:
                return gen_sensor_data([1000, 750, 500, 0], False)
        elif field == "lux":
            if count % 3 == 0:
                return gen_sensor_data([0, 250, 400, 500])
            elif count % 3 == 1:
                return gen_sensor_data([0, 4, 6, 8])
            else:
                return gen_sensor_data([0, 25, 200, 500], False)
        elif field == "solar_rad":
            return gen_sensor_data([300, 150, 50, 0])
        else:
            return gen_sensor_data([30, 20, 15, 0])

    fetch_data_mock.count = {}

    mocker.patch("sensor_graph.fetch_data", side_effect=fetch_data_mock)
    mocker.patch("power_graph.fetch_data", side_effect=fetch_data_mock)


def gen_sensor_data(value=[30, 34, 25, 20], valid=True):
    sensor_data = {"value": value, "time": [], "valid": valid}

    for i in range(len(value)):
        sensor_data["time"].append(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=i - len(value))
        )

    return sensor_data


# NOTE: テストを並列実行すると，この関数が結果を誤判定する可能性あり
def check_notify_slack(message, index=-1):
    import notify_slack

    notify_hist = notify_slack.hist_get()

    if message is None:
        assert notify_hist == [], "正常なはずなのに，エラー通知がされています．"
    else:
        assert len(notify_hist) != 0, "異常が発生したはずなのに，エラー通知がされていません．"
        assert notify_hist[index].find(message) != -1, "「{message}」が Slack で通知されていません．".format(
            message=message
        )


def save_image(request, img, index):
    from pil_util import convert_to_gray

    if index is None:
        file_name = "{test_name}.png".format(test_name=request.node.name)
    else:
        file_name = "{test_name}_{index}.png".format(test_name=request.node.name, index=index)

    convert_to_gray(img).save(EVIDENCE_DIR / file_name, "PNG")


def check_image(request, img, size, index=None):
    save_image(request, img, index)

    # NOTE: matplotlib で生成した画像の場合，期待値より 1pix 小さい場合がある
    assert (abs(img.size[0] - size["WIDTH"]) < 2) and (
        abs(img.size[1] - size["HEIGHT"]) < 2
    ), "画像サイズが期待値と一致しません．(期待値: {exp_x} x {exp_y}, 実際: {act_x} x {act_y})".format(
        exp_x=size["WIDTH"], exp_y=size["HEIGHT"], act_x=img.size[0], act_y=img.size[1]
    )


def load_test_config(config_file, tmp_path, request):
    config = load_config(config_file)

    config["LIVENESS"]["FILE"] = "{dir_path}/healthz-{name}".format(dir_path=tmp_path, name=request.node.name)
    pathlib.Path(config["LIVENESS"]["FILE"]).unlink(missing_ok=True)
    config["PANEL"]["UPDATE"]["INTERVAL"] = 60

    return config


def check_liveness(config, is_should_exist):
    healthz_file = pathlib.Path(config["LIVENESS"]["FILE"])

    if is_should_exist:
        assert healthz_file.exists(), "存在すべき healthz が存在しません．"
    else:
        assert not healthz_file.exists(), "存在してはいけない healthz が存在します．"


######################################################################
def test_create_image(request, mocker):
    import create_image

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        create_image.create_image(CONFIG_FILE, test_mode=True)[0],
        load_config(CONFIG_FILE)["PANEL"]["DEVICE"],
    )
    check_image(
        request, create_image.create_image(CONFIG_FILE)[0], load_config(CONFIG_FILE)["PANEL"]["DEVICE"]
    )

    check_notify_slack(None)


def test_create_image_small(request, mocker):
    import create_image

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        create_image.create_image(CONFIG_SMALL_FILE, test_mode=False)[0],
        load_config(CONFIG_SMALL_FILE)["PANEL"]["DEVICE"],
    )

    check_notify_slack(None)


def test_create_image_error(request, mocker):
    import create_image

    mock_sensor_fetch_data(mocker)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(CONFIG_FILE, small_mode=True, dummy_mode=True)[0],
        load_config(CONFIG_FILE)["PANEL"]["DEVICE"],
    )

    check_image(
        request,
        create_image.create_image(CONFIG_FILE)[0],
        load_config(CONFIG_FILE)["PANEL"]["DEVICE"],
    )

    check_notify_slack("Traceback")


# NOTE: テストの安定性に問題があるので複数リトライする
def test_create_image_influx_error(request, mocker):
    import time

    import create_image

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(CONFIG_FILE, small_mode=False, dummy_mode=True)[0],
        load_config(CONFIG_FILE)["PANEL"]["DEVICE"],
    )

    # NOTE: テスト結果を安定させるため，ウェイトを追加
    # (本当はちゃんとマルチスレッド対応した方が良いけど，単純に multiprocessing.Queue に置き換える
    # 方法を試したら何故かデッドロックが発生したので，お茶を濁す)
    time.sleep(1)

    # NOTE: sensor_graph と power_graph のそれぞれでエラーが発生
    check_notify_slack("Traceback", index=-1)
    check_notify_slack("Traceback", index=-2)


######################################################################
def test_weather_panel(request):
    import weather_panel

    check_image(
        request,
        weather_panel.create(load_config(CONFIG_SMALL_FILE), False)[0],
        load_config(CONFIG_SMALL_FILE)["WEATHER"]["PANEL"],
    )

    check_notify_slack(None)


def test_weather_panel_dummy(mocker, request):
    import copy

    import weather_panel

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

    check_image(
        request,
        weather_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["WEATHER"]["PANEL"],
    )

    check_notify_slack(None)


######################################################################
def test_wbgt_panel(request):
    import wbgt_panel

    check_image(
        request,
        wbgt_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["WBGT"]["PANEL"],
    )

    check_notify_slack(None)


def test_wbgt_panel_var(mocker, request):
    import wbgt_panel

    wbgt_info = gen_wbgt_info()
    for i in range(20, 34, 2):
        wbgt_info["current"] = i
        mocker.patch("wbgt_panel.get_wbgt", return_value=wbgt_info)
        check_image(
            request,
            wbgt_panel.create(load_config(CONFIG_FILE))[0],
            load_config(CONFIG_FILE)["WBGT"]["PANEL"],
            i,
        )

    check_notify_slack(None)


def test_wbgt_panel_error_1(freezer, mocker, request):
    import wbgt_panel

    # NOTE: 暑さ指数は夏のみ使うので，時期を変更
    freezer.move_to(datetime.datetime.now().replace(month=8))

    mocker.patch("weather_data.fetch_page", side_effect=RuntimeError())

    ret = wbgt_panel.create(load_config(CONFIG_FILE))
    check_image(request, ret[0], load_config(CONFIG_FILE)["WBGT"]["PANEL"])

    assert len(ret) == 3
    assert "Traceback" in ret[2]


def test_wbgt_panel_error_2(mocker, request):
    import wbgt_panel

    # NOTE: 暑さ指数は夏にしか取得できないので，冬はテストを見送る
    mon = datetime.datetime.now().month
    if (mon < 5) or (mon > 9):
        return

    mocker.patch("lxml.html.HtmlElement.xpath", return_value=[])

    ret = wbgt_panel.create(load_config(CONFIG_FILE))
    check_image(request, ret[0], load_config(CONFIG_FILE)["WBGT"]["PANEL"])

    assert len(ret) == 3
    assert "Traceback" in ret[2]


def test_wbgt_panel_error_3(mocker, request):
    import wbgt_panel

    # NOTE: 暑さ指数は夏にしか取得できないので，冬はテストを見送る
    mon = datetime.datetime.now().month
    if (mon < 5) or (mon > 9):
        return

    mock = mocker.patch("weather_data.datetime")
    mock.date.day.return_value = 100

    ret = wbgt_panel.create(load_config(CONFIG_FILE))
    check_image(request, ret[0], load_config(CONFIG_FILE)["WBGT"]["PANEL"])

    # NOTE: パネル生成処理としてはエラーにならない
    assert len(ret) == 2


######################################################################
def test_time_panel(request):
    import time_panel

    check_image(
        request,
        time_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["TIME"]["PANEL"],
    )

    check_notify_slack(None)


######################################################################
def test_create_power_graph(mocker, request):
    import power_graph

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        power_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["POWER"]["PANEL"],
        0,
    )

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    check_image(
        request,
        power_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["POWER"]["PANEL"],
        1,
    )

    check_notify_slack(None)


def test_create_power_graph_invalid(mocker, request):
    import power_graph

    mocker.patch("power_graph.fetch_data", return_value=gen_sensor_data([1000, 500, 0], False))

    check_image(
        request,
        power_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["POWER"]["PANEL"],
    )

    check_notify_slack(None)


def test_create_power_graph_error(mocker, request):
    import power_graph

    mocker.patch("power_graph.create_power_graph_impl", side_effect=RuntimeError())

    check_image(
        request,
        power_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["POWER"]["PANEL"],
    )

    check_notify_slack(None)


######################################################################
def test_create_sensor_graph_1(freezer, mocker, request):
    import sensor_graph

    mock_sensor_fetch_data(mocker)

    freezer.move_to(datetime.datetime.now().replace(hour=12))

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
        0,
    )

    freezer.move_to(datetime.datetime.now().replace(hour=20))

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
        1,
    )

    check_notify_slack(None)


def test_create_sensor_graph_2(freezer, mocker, request):
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

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
    )

    check_notify_slack(None)


def test_create_sensor_graph_dummy(freezer, mocker, request):
    import sensor_graph

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    mock_sensor_fetch_data(mocker)

    freezer.move_to(datetime.datetime.now().replace(hour=12))

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
        0,
    )

    freezer.move_to(datetime.datetime.now().replace(hour=20))

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
        1,
    )

    check_notify_slack(None)


def test_create_sensor_graph_invalid(mocker, request):
    import inspect

    import sensor_graph

    def dummy_data(db_config, measure, hostname, field, start, stop, last=False):
        dummy_data.i += 1
        if (dummy_data.i % 4 == 0) or (inspect.stack()[4].function == "get_aircon_power"):
            return gen_sensor_data(valid=False)
        else:
            return gen_sensor_data()

    dummy_data.i = 0

    mocker.patch("sensor_graph.fetch_data", side_effect=dummy_data)

    check_image(
        request,
        sensor_graph.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["SENSOR"]["PANEL"],
    )

    check_notify_slack(None)


def test_create_sensor_graph_influx_error(mocker, request):
    import sensor_graph

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    ret = sensor_graph.create(load_config(CONFIG_FILE))

    check_image(request, ret[0], load_config(CONFIG_FILE)["SENSOR"]["PANEL"])

    assert len(ret) == 3
    assert "Traceback" in ret[2]


######################################################################
def test_create_rain_cloud_panel(mocker, request):
    import rain_cloud_panel

    rain_cloud_panel.WINDOW_SIZE_CACHE.unlink(missing_ok=True)

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["RAIN_CLOUD"]["PANEL"],
        0,
    )

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_SMALL_FILE), is_side_by_side=False)[0],
        load_config(CONFIG_SMALL_FILE)["RAIN_CLOUD"]["PANEL"],
        1,
    )

    check_notify_slack(None)


def test_create_rain_cloud_panel_cache_and_error(mocker, request):
    import rain_cloud_panel
    from selenium_util import click_xpath as click_xpath_orig

    # NOTE: 6回だけエラーにする
    def click_xpath_mock(driver, xpath, wait=None, is_warn=True):
        click_xpath_mock.i += 1
        if click_xpath_mock.i <= 6:
            raise RuntimeError()
        else:
            return click_xpath_orig(driver, xpath, wait, is_warn)

    click_xpath_mock.i = 0

    mocker.patch("rain_cloud_panel.click_xpath", side_effect=click_xpath_mock)

    month_ago = datetime.datetime.now() + datetime.timedelta(days=-1)
    month_ago_epoch = month_ago.timestamp()

    if rain_cloud_panel.WINDOW_SIZE_CACHE.exists():
        rain_cloud_panel.WINDOW_SIZE_CACHE.touch()
        os.utime(str(rain_cloud_panel.WINDOW_SIZE_CACHE), (month_ago_epoch, month_ago_epoch))

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["RAIN_CLOUD"]["PANEL"],
        0,
    )

    mocker.patch("pickle.load", side_effect=RuntimeError())

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["RAIN_CLOUD"]["PANEL"],
        1,
    )

    check_notify_slack("Traceback")


def test_create_rain_cloud_panel_xpath_fail(mocker, request):
    import rain_cloud_panel
    from selenium_util import xpath_exists

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["RAIN_CLOUD"]["PANEL"],
    )

    # NOTE: エラー通知される可能性があるのでチェックは見送る
    # check_notify_slack(None)


def test_create_rain_cloud_panel_selenium_error(mocker, request):
    import rain_cloud_panel
    from selenium_util import create_driver_impl

    # NOTE: 一回だけエラーにする
    def create_driver_impl_mock(profile_name, data_path):
        create_driver_impl_mock.i += 1
        if create_driver_impl_mock.i == 1:
            raise RuntimeError()
        else:
            return create_driver_impl(profile_name, data_path)

    create_driver_impl_mock.i = 0

    mocker.patch("selenium_util.create_driver_impl", side_effect=create_driver_impl_mock)

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_SMALL_FILE))[0],
        load_config(CONFIG_SMALL_FILE)["RAIN_CLOUD"]["PANEL"],
    )

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので，None になる
    check_notify_slack(None)


def test_create_rain_cloud_panel_xpath_error(mocker, request):
    import rain_cloud_panel
    from selenium_util import xpath_exists

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_SMALL_FILE))[0],
        load_config(CONFIG_SMALL_FILE)["RAIN_CLOUD"]["PANEL"],
    )

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので，None になる
    check_notify_slack(None)


######################################################################
def test_slack_error(mocker, request):
    import create_image
    import slack_sdk

    mock_sensor_fetch_data(mocker)

    def webclient_mock(self, token):
        raise slack_sdk.errors.SlackClientError()

    mocker.patch.object(slack_sdk.web.client.WebClient, "__init__", webclient_mock)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(CONFIG_FILE, small_mode=True, dummy_mode=True)[0],
        load_config(CONFIG_FILE)["PANEL"]["DEVICE"],
    )

    check_notify_slack("Traceback")


def test_slack_error_with_image(mocker, request):
    import rain_cloud_panel
    from rain_cloud_panel import fetch_cloud_image

    def fetch_cloud_image_mock(driver, url, width, height, is_future=False):
        fetch_cloud_image_mock.i += 1
        if fetch_cloud_image_mock.i == 1:
            return fetch_cloud_image(driver, url, width, height, is_future)
        else:
            raise RuntimeError()

    fetch_cloud_image_mock.i = 0

    mocker.patch("rain_cloud_panel.fetch_cloud_image", side_effect=fetch_cloud_image_mock)

    check_image(
        request,
        rain_cloud_panel.create(load_config(CONFIG_FILE))[0],
        load_config(CONFIG_FILE)["RAIN_CLOUD"]["PANEL"],
    )

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
    import gzip
    import inspect
    import io

    import PIL.Image

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

    m = re.compile(r"{callback}\((.*)\)".format(callback=CALLBACK), re.MULTILINE | re.DOTALL).match(
        response.text
    )

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


def test_display_image(mocker, tmp_path, request):
    import builtins

    import display_image

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
            return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_test_config(CONFIG_SMALL_FILE, tmp_path, request)

    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    check_notify_slack(None)
    check_liveness(config, True)


def test_display_image_onetime(mocker, tmp_path, request):
    import builtins

    import display_image

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
            return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_test_config(CONFIG_FILE, tmp_path, request)

    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=False,
        test_mode=True,
        is_one_time=True,
    )

    check_notify_slack(None)
    check_liveness(config, True)


def test_display_image_error_major(mocker, tmp_path, request):
    import builtins

    import create_image
    import display_image

    ssh_client_mock = mocker.MagicMock()
    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=create_image.ERROR_CODE_MAJOR)

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
            return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_test_config(CONFIG_SMALL_FILE, tmp_path, request)

    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    # NOTE: 本来，create_image の中で通知されているので，上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, False)


def test_display_image_error_minor(mocker, tmp_path, request):
    import builtins

    import create_image
    import display_image

    ssh_client_mock = mocker.MagicMock()
    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=create_image.ERROR_CODE_MINOR)

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
            return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_test_config(CONFIG_SMALL_FILE, tmp_path, request)

    display_image.display_image(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    # NOTE: 本来，create_image の中で通知されているので，上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, True)


def test_display_image_error_unknown(mocker, tmp_path, request):
    import builtins

    import display_image

    ssh_client_mock = mocker.MagicMock()
    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=-1)

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
            return orig_open(file, mode, buffering, encoding, errors, newline, closefd, opener)

    mocker.patch("builtins.open", side_effect=open_mock)

    config = load_test_config(CONFIG_SMALL_FILE, tmp_path, request)

    with pytest.raises(SystemExit):
        display_image.display_image(
            config,
            "TEST",
            "TEST",
            CONFIG_FILE,
            small_mode=True,
            test_mode=True,
            is_one_time=False,
            prev_ssh=mocker.MagicMock(),
        )

    # NOTE: 本来，create_image の中で通知されているので，上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, False)
