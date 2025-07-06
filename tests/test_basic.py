#!/usr/bin/env python3
# ruff: noqa: S101
import datetime
import logging
import pathlib
import re
import zoneinfo
from unittest import mock

import my_lib.webapp.config
import pytest

my_lib.webapp.config.URL_PREFIX = "/weather_panel"

logging.getLogger("selenium.webdriver.remote").setLevel(logging.WARNING)
logging.getLogger("selenium.webdriver.common").setLevel(logging.DEBUG)


CONFIG_FILE = "config.example.yaml"
CONFIG_SMALL_FILE = "config-small.example.yaml"
EVIDENCE_DIR = pathlib.Path(__file__).parent / "evidence" / "image"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
TIMEZONE = zoneinfo.ZoneInfo("Asia/Tokyo")


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
    with (
        mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.chat_postMessage",
            return_value={"ok": True, "ts": "1234567890.123456"},
        ),
        mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_upload_v2",
            return_value={"ok": True, "files": [{"id": "test_file_id"}]},
        ),
        mock.patch(
            "my_lib.notify.slack.slack_sdk.web.client.WebClient.files_getUploadURLExternal",
            return_value={"ok": True, "upload_url": "https://example.com"},
        ) as fixture,
    ):
        yield fixture


@pytest.fixture(scope="session")
def app():
    import webui

    with mock.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"}):
        app = webui.create_app(CONFIG_FILE, CONFIG_SMALL_FILE, dummy_mode=True)

        yield app


@pytest.fixture
def config():
    import my_lib.config

    config_ = my_lib.config.load(CONFIG_FILE)
    config_["panel"]["update"]["interval"] = 60

    return config_


@pytest.fixture(autouse=True)
def _clear(config):
    import my_lib.footprint
    import my_lib.notify.slack

    my_lib.footprint.clear(config["liveness"]["file"]["display"])

    my_lib.notify.slack.interval_clear()
    my_lib.notify.slack.hist_clear()


@pytest.fixture
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


def mock_sensor_fetch_data(mocker):  # noqa: C901
    def fetch_data_mock(  # noqa: PLR0911, PLR0912, PLR0913
        db_config,  # noqa: ARG001
        measure,  # noqa: ARG001
        hostname,  # noqa: ARG001
        field,
        start="-30h",  # noqa: ARG001
        stop="now(TIMEZONE)",  # noqa: ARG001
        every_min=1,  # noqa: ARG001
        window_min=3,  # noqa: ARG001
        create_empty=True,  # noqa: ARG001
        last=False,  # noqa: ARG001
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

    # Mock for parallel fetch
    async def fetch_data_parallel_mock(db_config, requests):
        results = []
        for request in requests:
            result = fetch_data_mock(
                db_config,
                request.get("measure"),
                request.get("hostname"),
                request.get("field"),
                request.get("start", "-30h"),
                request.get("stop", "now()"),
                request.get("every_min", 1),
                request.get("window_min", 3),
                request.get("create_empty", True),
                request.get("last", False),
            )
            results.append(result)
        return results

    mocker.patch("weather_display.panel.sensor_graph.fetch_data", side_effect=fetch_data_mock)
    mocker.patch(
        "weather_display.panel.sensor_graph.fetch_data_parallel", side_effect=fetch_data_parallel_mock
    )
    mocker.patch("weather_display.panel.power_graph.fetch_data", side_effect=fetch_data_mock)


def gen_sensor_data(value=[30, 34, 25, 20], valid=True):  # noqa: B006
    sensor_data = {"value": value, "time": [], "valid": valid}

    for i in range(len(value)):
        sensor_data["time"].append(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=i - len(value))
        )

    return sensor_data


# NOTE: テストを並列実行すると、この関数が結果を誤判定する可能性あり
def check_notify_slack(message, index=-1):
    import my_lib.notify.slack

    notify_hist = my_lib.notify.slack.hist_get()

    if message is None:
        assert notify_hist == [], "正常なはずなのに、エラー通知がされています。"
    else:
        assert len(notify_hist) != 0, "異常が発生したはずなのに、エラー通知がされていません。"
        assert notify_hist[index].find(message) != -1, f"「{message}」が Slack で通知されていません。"


def save_image(request, img, index):
    import my_lib.pil_util

    file_name = f"{request.node.name}.png" if index is None else f"{request.node.name}_{index}.png"

    my_lib.pil_util.convert_to_gray(img).save(EVIDENCE_DIR / file_name, "PNG")


def check_image(request, img, size, index=None):
    save_image(request, img, index)

    # NOTE: matplotlib で生成した画像の場合、期待値より 1pix 小さい場合がある
    assert abs(img.size[0] - size["width"]) < 2
    assert abs(img.size[1] - size["height"]) < 2, (
        "画像サイズが期待値と一致しません。"
        f"""(期待値: {size["width"]} x {size["height"]}, 実際: {img.size[0]} x {img.size[1]})"""
    )


def check_liveness(config, is_should_healthy):
    import healthz

    liveness = healthz.check_liveness(
        [
            {
                "name": name,
                "liveness_file": pathlib.Path(config["liveness"]["file"][name]),
                "interval": config["panel"]["update"]["interval"],
            }
            for name in ["display"]
        ]
    )

    if is_should_healthy:
        assert liveness, "Liveness が更新されていません。"
    else:
        assert not liveness, "Liveness が更新されてしまっています。"


######################################################################
def test_create_image(request, mocker, config):
    import create_image

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        create_image.create_image(config, test_mode=True)[0],
        config["panel"]["device"],
    )
    check_image(
        request,
        create_image.create_image(config)[0],
        config["panel"]["device"],
    )

    check_notify_slack(None)


def test_create_image_small(request, config, mocker):
    import create_image

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        create_image.create_image(config, test_mode=False)[0],
        config["panel"]["device"],
    )

    check_notify_slack(None)


def test_create_image_error(request, config, mocker):
    import create_image

    mock_sensor_fetch_data(mocker)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(config, small_mode=True, dummy_mode=True)[0],
        config["panel"]["device"],
    )

    check_image(
        request,
        create_image.create_image(config)[0],
        config["panel"]["device"],
    )

    check_notify_slack("Traceback")


# NOTE: テストの安定性に問題があるので複数リトライする
def test_create_image_influx_error(request, config, mocker):
    import time

    import create_image

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(config, small_mode=False, dummy_mode=True)[0],
        config["panel"]["device"],
    )

    # NOTE: テスト結果を安定させるため、ウェイトを追加
    # (本当はちゃんとマルチスレッド対応した方が良いけど、単純に multiprocessing.Queue に置き換える
    # 方法を試したら何故かデッドロックが発生したので、お茶を濁す)
    time.sleep(1)

    # NOTE: sensor_graph と power_graph のそれぞれでエラーが発生
    check_notify_slack("Traceback", index=-1)
    check_notify_slack("Traceback", index=-2)


######################################################################
def test_weather_panel(request, config):
    import weather_display.panel.weather

    check_image(
        request,
        weather_display.panel.weather.create(config, False)[0],
        config["weather"]["panel"],
    )

    check_notify_slack(None)


def test_weather_panel_dummy(mocker, request, config):
    import copy

    import weather_display.panel.weather

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

    mocker.patch("weather_display.panel.weather.get_weather_yahoo", return_value=weather_info)
    mocker.patch("weather_display.panel.weather.get_clothing_yahoo", return_value=clothing_info)
    mocker.patch("weather_display.panel.weather.get_wbgt", return_value=wbgt_info)

    check_image(
        request,
        weather_display.panel.weather.create(config)[0],
        config["weather"]["panel"],
    )

    check_notify_slack(None)


######################################################################
def test_wbgt_panel(request, config):
    import weather_display.panel.wbgt

    check_image(
        request,
        weather_display.panel.wbgt.create(config)[0],
        config["wbgt"]["panel"],
    )

    check_notify_slack(None)


def test_wbgt_panel_var(mocker, request, config):
    import weather_display.panel.wbgt

    wbgt_info = gen_wbgt_info()
    for i in range(20, 34, 2):
        wbgt_info["current"] = i
        mocker.patch("weather_display.panel.wbgt.get_wbgt", return_value=wbgt_info)
        check_image(
            request,
            weather_display.panel.wbgt.create(config)[0],
            config["wbgt"]["panel"],
            i,
        )

    check_notify_slack(None)


def test_wbgt_panel_error_1(time_machine, mocker, request, config):
    import weather_display.panel.wbgt

    # NOTE: 暑さ指数は夏のみ使うので、時期を変更
    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(month=8))

    mocker.patch("my_lib.weather.fetch_page", side_effect=RuntimeError())

    ret = weather_display.panel.wbgt.create(config)
    check_image(request, ret[0], config["wbgt"]["panel"])

    assert len(ret) == 3
    assert "Traceback" in ret[2]


def test_wbgt_panel_error_2(mocker, request, config):
    import weather_display.panel.wbgt

    mocker.patch("lxml.html.HtmlElement.xpath", return_value=[])

    ret = weather_display.panel.wbgt.create(config)
    check_image(request, ret[0], config["wbgt"]["panel"])

    # NOTE: ページのフォーマットが期待値と異なるくらいではエラーにしない
    assert len(ret) == 2


######################################################################
def test_time_panel(request, config):
    import weather_display.panel.time

    check_image(
        request,
        weather_display.panel.time.create(config)[0],
        config["time"]["panel"],
    )

    check_notify_slack(None)


######################################################################
def test_create_power_graph(mocker, request, config):
    import weather_display.panel.power_graph

    mock_sensor_fetch_data(mocker)

    check_image(
        request,
        weather_display.panel.power_graph.create(config)[0],
        config["power"]["panel"],
        0,
    )

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    check_image(
        request,
        weather_display.panel.power_graph.create(config)[0],
        config["power"]["panel"],
        1,
    )

    check_notify_slack(None)


def test_create_power_graph_invalid(mocker, request, config):
    import weather_display.panel.power_graph

    mocker.patch(
        "weather_display.panel.power_graph.fetch_data", return_value=gen_sensor_data([1000, 500, 0], False)
    )

    check_image(
        request,
        weather_display.panel.power_graph.create(config)[0],
        config["power"]["panel"],
    )

    check_notify_slack(None)


def test_create_power_graph_error(mocker, request, config):
    import weather_display.panel.power_graph

    mocker.patch("weather_display.panel.power_graph.create_power_graph_impl", side_effect=RuntimeError())

    check_image(
        request,
        weather_display.panel.power_graph.create(config)[0],
        config["power"]["panel"],
    )

    check_notify_slack(None)


######################################################################
def test_create_sensor_graph_1(time_machine, mocker, request, config):
    import weather_display.panel.sensor_graph

    mock_sensor_fetch_data(mocker)

    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(hour=12))

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
        0,
    )

    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(hour=20))

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
        1,
    )

    check_notify_slack(None)


def test_create_sensor_graph_2(time_machine, mocker, request, config):
    import weather_display.panel.sensor_graph

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

    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(hour=12))

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
    )

    check_notify_slack(None)


def test_create_sensor_graph_dummy(time_machine, mocker, request, config):
    import weather_display.panel.sensor_graph

    mocker.patch.dict("os.environ", {"DUMMY_MODE": "true"})

    mock_sensor_fetch_data(mocker)

    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(hour=12))

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
        0,
    )

    time_machine.move_to(datetime.datetime.now(TIMEZONE).replace(hour=20))

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
        1,
    )

    check_notify_slack(None)


def test_create_sensor_graph_invalid(mocker, request, config):
    import inspect

    import weather_display.panel.sensor_graph

    def dummy_data(db_config, measure, hostname, field, start, stop, last=False):  # noqa: ARG001,PLR0913
        dummy_data.i += 1
        if (dummy_data.i % 4 == 0) or (inspect.stack()[4].function == "get_aircon_power"):
            return gen_sensor_data(valid=False)
        else:
            return gen_sensor_data()

    dummy_data.i = 0

    mocker.patch("weather_display.panel.sensor_graph.fetch_data", side_effect=dummy_data)

    check_image(
        request,
        weather_display.panel.sensor_graph.create(config)[0],
        config["sensor"]["panel"],
    )

    check_notify_slack(None)


def test_create_sensor_graph_influx_error(mocker, request, config):
    import weather_display.panel.sensor_graph

    mocker.patch("influxdb_client.InfluxDBClient.query_api", side_effect=RuntimeError())

    ret = weather_display.panel.sensor_graph.create(config)

    check_image(request, ret[0], config["sensor"]["panel"])

    assert len(ret) == 3
    assert "Traceback" in ret[2]


######################################################################
def test_create_rain_cloud_panel(request, config):
    import weather_display.panel.rain_cloud

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config)[0],
        config["rain_cloud"]["panel"],
        0,
    )

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config, is_side_by_side=False)[0],
        config["rain_cloud"]["panel"],
        1,
    )

    check_notify_slack(None)


def test_create_rain_cloud_panel_cache_and_error(mocker, request, config):
    from my_lib.selenium_util import click_xpath as click_xpath_orig

    import weather_display.panel.rain_cloud

    # NOTE: 6回だけエラーにする
    def click_xpath_mock(driver, xpath, wait=None, is_warn=True):
        click_xpath_mock.i += 1
        if click_xpath_mock.i <= 6:
            raise RuntimeError

        return click_xpath_orig(driver, xpath, wait, is_warn)

    click_xpath_mock.i = 0

    mocker.patch("weather_display.panel.rain_cloud.click_xpath", side_effect=click_xpath_mock)
    mocker.patch("weather_display.panel.rain_cloud.time.sleep")  # Mock time.sleep to prevent timeout

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config, True, False)[0],
        config["rain_cloud"]["panel"],
        0,
    )

    mocker.patch("pickle.load", side_effect=RuntimeError())

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config)[0],
        config["rain_cloud"]["panel"],
        1,
    )

    check_notify_slack("Traceback")


def test_create_rain_cloud_panel_xpath_fail(mocker, request, config):
    from my_lib.selenium_util import xpath_exists

    import weather_display.panel.rain_cloud

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("my_lib.selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config)[0],
        config["rain_cloud"]["panel"],
    )

    # NOTE: エラー通知される可能性があるのでチェックは見送る
    # check_notify_slack(None)


def test_create_rain_cloud_panel_selenium_error(mocker, request, config):
    from my_lib.selenium_util import create_driver_impl

    import weather_display.panel.rain_cloud

    # NOTE: 一回だけエラーにする
    def create_driver_impl_mock(profile_name, data_path):
        create_driver_impl_mock.i += 1
        if create_driver_impl_mock.i == 1:
            raise RuntimeError

        return create_driver_impl(profile_name, data_path)

    create_driver_impl_mock.i = 0

    mocker.patch("my_lib.selenium_util.create_driver_impl", side_effect=create_driver_impl_mock)

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config)[0],
        config["rain_cloud"]["panel"],
    )

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので、None になる
    check_notify_slack(None)


def test_create_rain_cloud_panel_xpath_error(mocker, request, config):
    from my_lib.selenium_util import xpath_exists

    import weather_display.panel.rain_cloud

    # NOTE: 一回だけエラーにする
    def xpath_exists_mock(driver, xpath):
        xpath_exists_mock.i += 1
        if xpath_exists_mock.i == 1:
            return False
        else:
            return xpath_exists(driver, xpath)

    xpath_exists_mock.i = 0

    mocker.patch("my_lib.selenium_util.xpath_exists", side_effect=xpath_exists_mock)

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config)[0],
        config["rain_cloud"]["panel"],
    )

    # NOTE: CONFIG_SMALL_FILE には Slack の設定がないので、None になる
    check_notify_slack(None)


######################################################################
def test_slack_error(mocker, request, config):
    import slack_sdk

    import create_image

    mock_sensor_fetch_data(mocker)

    def webclient_mock(self, token):  # noqa: ARG001
        raise slack_sdk.errors.SlackClientError

    mocker.patch.object(slack_sdk.web.client.WebClient, "__init__", webclient_mock)
    mocker.patch("create_image.draw_panel", side_effect=RuntimeError())

    check_image(
        request,
        create_image.create_image(config, small_mode=True, dummy_mode=True)[0],
        config["panel"]["device"],
    )

    check_notify_slack("Traceback")


def test_slack_error_with_image(mocker, request, config):
    from my_lib.selenium_util import click_xpath as click_xpath_orig

    import weather_display.panel.rain_cloud

    # NOTE: 6回だけエラーにする（test_create_rain_cloud_panel_cache_and_errorと同じアプローチ）
    def click_xpath_mock(driver, xpath, wait=None, is_warn=True):
        click_xpath_mock.i += 1
        if click_xpath_mock.i <= 6:
            raise RuntimeError("Test error for Slack image notification")  # noqa: EM101, TRY003

        return click_xpath_orig(driver, xpath, wait, is_warn)

    click_xpath_mock.i = 0

    mocker.patch("weather_display.panel.rain_cloud.click_xpath", side_effect=click_xpath_mock)
    mocker.patch("weather_display.panel.rain_cloud.time.sleep")  # Mock time.sleep to prevent timeout

    check_image(
        request,
        weather_display.panel.rain_cloud.create(config, True, False)[0],
        config["rain_cloud"]["panel"],
    )

    check_notify_slack("Traceback")


######################################################################
def test_redirect(client):
    response = client.get("/")
    assert response.status_code == 302
    assert re.search(rf"{my_lib.webapp.config.URL_PREFIX}/$", response.location)


def test_index(client):
    response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/")
    assert response.status_code == 200
    assert "気象パネル画像" in response.data.decode("utf-8")

    response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200


def test_index_with_other_status(client, mocker):
    mocker.patch(
        "flask.wrappers.Response.status_code",
        return_value=301,
        new_callable=mocker.PropertyMock,
    )

    response = client.get(f"{my_lib.webapp.config.URL_PREFIX}/", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 301


def test_api_run(client, mocker):
    import gzip
    import inspect
    import io

    import PIL.Image

    def dummy_time():
        dummy_time.i += 1
        if (dummy_time.i == 1) or (inspect.stack()[4].function == "generate_image"):
            return (datetime.datetime.now(TIMEZONE) + datetime.timedelta(days=-1)).timestamp()
        else:
            return datetime.datetime.now(TIMEZONE).timestamp()

    dummy_time.i = 0

    mocker.patch("time.time", side_effect=dummy_time)

    # NOTE: 1回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]
    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    # NOTE: 2回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    # NOTE: 3回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200
    token = response.json["token"]

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()

    response = client.post(
        f"{my_lib.webapp.config.URL_PREFIX}/api/image",
        headers={"Accept-Encoding": "gzip"},
        data={"token": token},
    )
    assert response.status_code == 200
    image_data = gzip.decompress(response.data)
    # NOTE: サイズが適度にあり、PNG として解釈できれば OK とする
    assert len(image_data) > 1024
    assert PIL.Image.open(io.BytesIO(image_data)).size == (3200, 1800)


def test_api_run_small(client, mocker):
    import inspect
    import json

    CALLBACK = "TEST"

    def dummy_time():
        dummy_time.i += 1
        if (dummy_time.i == 1) or (inspect.stack()[4].function == "generate_image"):
            return (datetime.datetime.now(TIMEZONE) + datetime.timedelta(days=-1)).timestamp()
        else:
            return datetime.datetime.now(TIMEZONE).timestamp()

    dummy_time.i = 0

    mocker.patch("time.time", side_effect=dummy_time)

    # NOTE: 1回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "mode": "small",
            "callback": CALLBACK,
        },
    )
    assert response.status_code == 200

    m = re.compile(rf"{CALLBACK}\((.*)\)", re.MULTILINE | re.DOTALL).match(response.text)

    assert m is not None

    token = json.loads(m.group(1))["token"]

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    assert response.data.decode()


def test_api_run_error(client, mocker):
    mocker.patch("weather_display.runner.webapi.run.generate_image", side_effect=RuntimeError())

    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={"test": True, "mode": "small"},
    )
    assert response.status_code == 200

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": "TEST"})
    assert response.status_code == 200

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/image", data={"token": "TEST"})
    assert response.status_code == 200


def test_api_run_normal(mocker):
    import inspect

    import webui

    # NOTE: fixture の方はダミーモード固定で動かしているので、
    # ここではノーマルモードで webapp を動かしてテストする。
    mocker.patch.dict("os.environ", {"WERKZEUG_RUN_MAIN": "true"})
    app = webui.create_app(CONFIG_FILE, CONFIG_SMALL_FILE)
    client = app.test_client()

    def dummy_time():
        dummy_time.i += 1
        if (dummy_time.i == 1) or (inspect.stack()[4].function == "generate_image"):
            return (datetime.datetime.now(TIMEZONE) + datetime.timedelta(days=-1)).timestamp()
        else:
            return datetime.datetime.now(TIMEZONE).timestamp()

    dummy_time.i = 0

    mocker.patch("time.time", side_effect=dummy_time)

    # NOTE: 1回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]
    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ。
    response.data.decode()

    # NOTE: 2回目
    response = client.get(
        f"{my_lib.webapp.config.URL_PREFIX}/api/run",
        query_string={
            "mode": "small",
            "test": True,
        },
    )
    assert response.status_code == 200

    token = response.json["token"]

    response = client.post(f"{my_lib.webapp.config.URL_PREFIX}/api/log", data={"token": token})
    assert response.status_code == 200
    # NOTE: ログを出し切るまで待つ
    response.data.decode()

    client.delete()


######################################################################
@pytest.mark.xdist_group(name="Selenium")
def test_display_image(mocker, config):
    import builtins

    import display_image

    ssh_mock = mocker.MagicMock()

    stdin_mock = mocker.MagicMock()
    stdout_mock = mocker.MagicMock()
    stderr_mock = mocker.MagicMock()
    stdout_mock.channel.recv_exit_status.return_value = 0

    ssh_mock.exec_command.return_value = (stdin_mock, stdout_mock, stderr_mock)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", return_value=ssh_mock)

    orig_open = builtins.open

    def open_mock(  # noqa: PLR0913
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

    display_image.execute(
        config,
        "TEST",
        "TEST",
        CONFIG_SMALL_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    check_notify_slack(None)
    check_liveness(config, True)


@pytest.mark.xdist_group(name="Selenium")
def test_display_image_onetime(mocker, config):
    import builtins

    import display_image

    ssh_mock = mocker.MagicMock()

    stdin_mock = mocker.MagicMock()
    stdout_mock = mocker.MagicMock()
    stderr_mock = mocker.MagicMock()
    stdout_mock.channel.recv_exit_status.return_value = 0

    ssh_mock.exec_command.return_value = (stdin_mock, stdout_mock, stderr_mock)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", return_value=ssh_mock)

    orig_open = builtins.open

    def open_mock(  # noqa: PLR0913
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

    display_image.execute(
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


@pytest.mark.xdist_group(name="Selenium")
def test_display_image_error_major(mocker, config):
    import builtins

    import create_image
    import display_image

    ssh_mock = mocker.MagicMock()

    stdin_mock = mocker.MagicMock()
    stdout_mock = mocker.MagicMock()
    stderr_mock = mocker.MagicMock()
    stdout_mock.channel.recv_exit_status.return_value = 0

    ssh_mock.exec_command.return_value = (stdin_mock, stdout_mock, stderr_mock)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", return_value=ssh_mock)

    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=create_image.ERROR_CODE_MAJOR)

    mocker.patch("subprocess.Popen", return_value=subprocess_popen_mock)

    orig_open = builtins.open

    def open_mock(  # noqa: PLR0913
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

    display_image.execute(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    # NOTE: 本来、create_image の中で通知されているので、上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, False)


def test_display_image_error_minor(mocker, config):
    import builtins

    import create_image
    import display_image

    ssh_mock = mocker.MagicMock()

    stdin_mock = mocker.MagicMock()
    stdout_mock = mocker.MagicMock()
    stderr_mock = mocker.MagicMock()
    stdout_mock.channel.recv_exit_status.return_value = 0

    ssh_mock.exec_command.return_value = (stdin_mock, stdout_mock, stderr_mock)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", return_value=ssh_mock)

    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=create_image.ERROR_CODE_MINOR)

    mocker.patch("subprocess.Popen", return_value=subprocess_popen_mock)

    orig_open = builtins.open

    def open_mock(  # noqa: PLR0913
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

    display_image.execute(
        config,
        "TEST",
        "TEST",
        CONFIG_FILE,
        small_mode=True,
        test_mode=True,
        is_one_time=False,
        prev_ssh=mocker.MagicMock(),
    )

    # NOTE: 本来、create_image の中で通知されているので、上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, True)


def test_display_image_error_unknown(mocker, config):
    import builtins

    import display_image

    ssh_mock = mocker.MagicMock()

    stdin_mock = mocker.MagicMock()
    stdout_mock = mocker.MagicMock()
    stderr_mock = mocker.MagicMock()
    stdout_mock.channel.recv_exit_status.return_value = 0

    ssh_mock.exec_command.return_value = (stdin_mock, stdout_mock, stderr_mock)

    mocker.patch("paramiko.RSAKey.from_private_key")
    mocker.patch("paramiko.SSHClient", return_value=ssh_mock)

    subprocess_popen_mock = mocker.MagicMock()
    type(subprocess_popen_mock).returncode = mocker.PropertyMock(return_value=-1)

    mocker.patch("subprocess.Popen", return_value=subprocess_popen_mock)

    orig_open = builtins.open

    def open_mock(  # noqa: PLR0913
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

    with pytest.raises(SystemExit):
        display_image.execute(
            config,
            "TEST",
            "TEST",
            CONFIG_FILE,
            small_mode=True,
            test_mode=True,
            is_one_time=False,
            prev_ssh=mocker.MagicMock(),
        )

    # NOTE: 本来、create_image の中で通知されているので、上記の故障注入方法では通知はされない
    check_notify_slack(None)
    check_liveness(config, False)
