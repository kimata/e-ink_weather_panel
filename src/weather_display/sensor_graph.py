#!/usr/bin/env python3
"""
センサーグラフを生成します。

Usage:
  sensor_graph.py [-c CONFIG] -o PNG_FILE [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o PNG_FILE       : 生成した画像を指定されたパスに保存します。
  -D                : デバッグモードで動作します。
"""

import asyncio
import datetime
import functools
import io
import logging
import os
import pathlib
import time
import traceback

import matplotlib  # noqa: ICN001
import matplotlib.dates
import matplotlib.gridspec
import matplotlib.offsetbox
import matplotlib.pyplot  # noqa: ICN001
import my_lib.panel_util
import pandas.plotting
import PIL.Image
from my_lib.sensor_data import fetch_data, fetch_data_parallel

matplotlib.use("Agg")

pandas.plotting.register_matplotlib_converters()

IMAGE_DPI = 100.0
EMPTY_VALUE = -100.0

AIRCON_WORK_THRESHOLD = 30


@functools.lru_cache(maxsize=8)
def get_shared_axis_config():
    """共通の軸設定を返す（キャッシュ付き）"""
    return {
        "major_locator": matplotlib.dates.DayLocator(interval=1),
        "major_formatter": matplotlib.dates.DateFormatter("%-d"),
    }


@functools.lru_cache(maxsize=32)
def _get_font_properties(font_path_str, size):
    """フォントプロパティをキャッシュ付きで取得"""
    return matplotlib.font_manager.FontProperties(fname=font_path_str, size=size)


def get_plot_font(config, font_type, size):
    font_path = pathlib.Path(config["path"]).resolve() / config["map"][font_type]

    # 初回アクセス時のみログ出力
    cache_info = _get_font_properties.cache_info()

    # キャッシュ統計を使って初回判定
    result = _get_font_properties(str(font_path), size)
    new_cache_info = _get_font_properties.cache_info()

    # キャッシュミスが増えた場合は新しいフォントのロード
    if new_cache_info.misses > cache_info.misses:
        logging.info("Load font: %s (cached)", font_path)

    return result


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "jp_bold", 34),
        "value": get_plot_font(font_config, "en_cond", 65),
        "value_small": get_plot_font(font_config, "en_cond", 55),
        "value_unit": get_plot_font(font_config, "jp_regular", 18),
        "yaxis": get_plot_font(font_config, "jp_regular", 20),
        "xaxis": get_plot_font(font_config, "en_medium", 20),
    }


def plot_item(ax, title, unit, data, xbegin_numeric, ylim, fmt, scale, small, face_map, axis_config):  # noqa: PLR0913
    logging.info("Plot %s", title)

    # 事前に数値化された時間データを使用
    x = data["time_numeric"] if "time_numeric" in data else data["time"]
    y = data["value"]

    if not data["valid"]:
        text = "?"
    else:
        # NOTE: 下記の next の記法だとカバレッジが正しく取れない
        text = fmt.format(next((item for item in reversed(y) if item is not None), None))  # pragma: no cover

    if scale == "log":
        # NOTE: エラーが出ないように値を補正
        y = [1 if (i is None or i < 1) else i for i in y]

    if title is not None:
        ax.set_title(title, fontproperties=face_map["title"], color="#333333")

    ax.set_ylim(ylim)

    # 数値化済みの時間範囲を設定
    if "time_numeric" in data and len(data["time_numeric"]) > 0:
        # 3時間分のマージンを数値で追加（3時間 = 3/24日）
        ax.set_xlim([xbegin_numeric, data["time_numeric"][-1] + 3 / 24])
    else:
        # フォールバック：従来の方式
        logging.warning("数値化済み時間データが利用できないため、フォールバック処理を実行します")
        if isinstance(x, list) and len(x) > 0:
            if isinstance(x[-1], datetime.datetime):
                logging.warning("datetime型の時間データをその場で数値化して使用します")
                ax.set_xlim([xbegin_numeric, matplotlib.dates.date2num(x[-1]) + 3 / 24])
            else:
                logging.warning("時間データを数値として直接使用します")
                ax.set_xlim([xbegin_numeric, x[-1] + 3 / 24])
        else:
            # さらなるフォールバック
            logging.warning("時間データが無効なため、固定の時間範囲を設定します")
            ax.set_xlim([xbegin_numeric, xbegin_numeric + 3])

    ax.plot(
        x,
        y,
        color="#CCCCCC",
        marker="o",
        markevery=[len(y) - 1],
        markersize=5,
        markerfacecolor="#DDDDDD",
        markeredgewidth=3,
        markeredgecolor="#BBBBBB",
        linewidth=3.0,
        linestyle="solid",
    )

    ax.fill_between(x, y, 0, facecolor="#DDDDDD", alpha=0.5)

    font = face_map["value_small"] if small else face_map["value"]

    # 共有された軸設定を使用
    ax.xaxis.set_major_locator(axis_config["major_locator"])
    ax.xaxis.set_major_formatter(axis_config["major_formatter"])
    for label in ax.get_xticklabels():
        label.set_fontproperties(face_map["xaxis"])

    ax.set_ylabel(unit, fontproperties=face_map["yaxis"])
    ax.set_yscale(scale)

    ax.grid(axis="x", color="#000000", alpha=0.1, linestyle="-", linewidth=1)

    ax.text(
        0.92,
        0.05,
        text,
        transform=ax.transAxes,
        horizontalalignment="right",
        color="#000000",
        alpha=0.8,
        fontproperties=font,
    )

    # ax.text(0.92-len(unit)*0.09, 0.05, text,
    #         transform=ax.transAxes, horizontalalignment='right',
    #         color='#000000', alpha=0.8,
    #         fontproperties=font)

    # ax.text(0.98, 0.05, unit,
    #         transform=ax.transAxes, horizontalalignment='right',
    #         color='#000000', alpha=0.8,
    #         fontproperties=face_map['value_unit'])

    ax.label_outer()


def get_aircon_power_requests(room_list):
    """エアコン電力取得用のリクエストリストを生成"""
    aircon_requests = []
    aircon_map = {}

    if os.environ.get("DUMMY_MODE", "false") == "true":
        start = "-169h"
        stop = "-168h"
    else:
        start = "-1h"
        stop = "now()"

    for col, room in enumerate(room_list):
        if "aircon" in room:
            request_index = len(aircon_requests)
            aircon_map[col] = request_index
            aircon_requests.append(
                {
                    "measure": room["aircon"]["measure"],
                    "hostname": room["aircon"]["hostname"],
                    "field": "power",
                    "start": start,
                    "stop": stop,
                    "last": True,
                }
            )

    return aircon_requests, aircon_map


def get_aircon_power_from_results(results, aircon_map, col):
    """並列取得結果からエアコン電力を取得"""
    if col not in aircon_map:
        return None

    data = results[aircon_map[col]]
    if data["valid"]:
        return data["value"][0]
    else:
        return None


def draw_aircon_icon(ax, power, icon_config):
    if (power is None) or (power < AIRCON_WORK_THRESHOLD):
        return

    icon_file = icon_config["aircon"]["path"]

    img = matplotlib.pyplot.imread(str(pathlib.Path(icon_file)))

    imagebox = matplotlib.offsetbox.OffsetImage(img, zoom=0.3)
    imagebox.image.axes = ax

    ab = matplotlib.offsetbox.AnnotationBbox(
        offsetbox=imagebox,
        box_alignment=(0, 1),
        xycoords="axes fraction",
        xy=(0.05, 0.95),
        frameon=False,
    )
    ax.add_artist(ab)


def draw_light_icon(ax, lux_list, icon_config):
    # NOTE: 下記の next の記法だとカバレッジが正しく取れない
    lux = next((item for item in reversed(lux_list) if item is not None), None)  # pragma: no cover

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))
    # NOTE: 昼間はアイコンを描画しない
    if (now.hour > 7) and (now.hour < 17):
        return

    if lux == EMPTY_VALUE:
        return
    elif lux < 10:
        icon_file = icon_config["light"]["off"]["path"]
    else:
        icon_file = icon_config["light"]["on"]["path"]

    img = matplotlib.pyplot.imread(str(pathlib.Path(icon_file)))

    imagebox = matplotlib.offsetbox.OffsetImage(img, zoom=0.25)
    imagebox.image.axes = ax

    ab = matplotlib.offsetbox.AnnotationBbox(
        offsetbox=imagebox,
        box_alignment=(0, 1),
        xycoords="axes fraction",
        xy=(0, 1),
        frameon=False,
    )
    ax.add_artist(ab)


def sensor_data(db_config, host_specify_list, param):
    if os.environ.get("DUMMY_MODE", "false") == "true":
        period_start = "-228h"
        period_stop = "-168h"
    else:
        period_start = "-60h"
        period_stop = "now()"

    for host_specify in host_specify_list:
        data = fetch_data(
            db_config,
            host_specify["measure"],
            host_specify["hostname"],
            param,
            period_start,
            period_stop,
        )
        if data["valid"]:
            return data
    return data


def create_sensor_graph_impl(panel_config, font_config, db_config):  # noqa: C901, PLR0912, PLR0915
    face_map = get_face_map(font_config)

    room_list = panel_config["room_list"]
    width = panel_config["panel"]["width"]
    height = panel_config["panel"]["height"]

    matplotlib.pyplot.style.use("grayscale")

    fig = matplotlib.pyplot.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    # NOTE: 全データを並列で一度に取得してキャッシュ（最適化）
    data_cache = {}
    cache = None
    range_map = {}
    time_begin = datetime.datetime.now(datetime.timezone.utc)

    # 並列取得用のリクエストリストを準備
    fetch_requests = []
    request_map = {}  # (param_name, col) -> request_index のマッピング

    for param in panel_config["param_list"]:
        data_cache[param["name"]] = {}
        for col in range(len(room_list)):
            for host_specify in room_list[col]["sensor"]:
                request_index = len(fetch_requests)
                request_map[(param["name"], col, host_specify["measure"], host_specify["hostname"])] = (
                    request_index
                )

                if os.environ.get("DUMMY_MODE", "false") == "true":
                    period_start = "-228h"
                    period_stop = "-168h"
                else:
                    period_start = "-60h"
                    period_stop = "now()"

                fetch_requests.append(
                    {
                        "measure": host_specify["measure"],
                        "hostname": host_specify["hostname"],
                        "field": param["name"],
                        "start": period_start,
                        "stop": period_stop,
                    }
                )

    # エアコン電力取得用のリクエストも追加
    aircon_requests, aircon_map = get_aircon_power_requests(room_list)

    all_requests = fetch_requests + aircon_requests
    aircon_results_offset = len(fetch_requests)

    # 並列でデータを取得
    logging.info(
        "Fetching sensor data in parallel (%d requests, %d aircon)", len(fetch_requests), len(aircon_requests)
    )
    parallel_start = time.perf_counter()
    all_results = asyncio.run(fetch_data_parallel(db_config, all_requests))
    parallel_time = time.perf_counter() - parallel_start
    logging.info("Parallel fetch completed in %.2f seconds", parallel_time)

    # センサーデータとエアコンデータを分離
    results = all_results[: len(fetch_requests)]
    aircon_results = all_results[aircon_results_offset:] if aircon_requests else []

    # 結果をキャッシュに格納（sensor_data関数のロジックを適用）
    for param in panel_config["param_list"]:
        for col in range(len(room_list)):
            # 複数のセンサーから最初の有効なデータを選択
            data = None
            for host_specify in room_list[col]["sensor"]:
                request_key = (param["name"], col, host_specify["measure"], host_specify["hostname"])
                if request_key in request_map:
                    request_index = request_map[request_key]
                    candidate_data = results[request_index]
                    if candidate_data["valid"]:
                        data = candidate_data
                        break

            # 有効なデータが見つからない場合は最後のデータを使用
            if data is None and room_list[col]["sensor"]:
                last_host = room_list[col]["sensor"][-1]
                request_key = (param["name"], col, last_host["measure"], last_host["hostname"])
                if request_key in request_map:
                    request_index = request_map[request_key]
                    data = results[request_index]

            data_cache[param["name"]][col] = data if data else {"valid": False, "time": [], "value": []}

            if data and data["valid"]:
                # 日付を数値化（最適化）
                if data["time"]:
                    data["time_numeric"] = matplotlib.dates.date2num(data["time"])
                else:
                    data["time_numeric"] = []

                if data["time"][0] < time_begin:
                    time_begin = data["time"][0]
                if cache is None:
                    cache = {
                        "time": data["time"],
                        "time_numeric": data.get("time_numeric", []),
                        "value": [EMPTY_VALUE for x in range(len(data["time"]))],
                        "valid": False,
                    }

    # キャッシュからレンジを計算
    for param in panel_config["param_list"]:
        param_min = float("inf")
        param_max = -float("inf")

        for col in range(len(room_list)):
            data = data_cache[param["name"]][col]
            if not data["valid"]:
                continue

            min_val = min([item for item in data["value"] if item is not None])
            max_val = max([item for item in data["value"] if item is not None])
            if min_val < param_min:
                param_min = min_val
            if max_val > param_max:
                param_max = max_val

        # NOTE: 見やすくなるように、ちょっと広げる
        range_map[param["name"]] = [
            max(0, param_min - (param_max - param_min) * 0.3),
            param_max + (param_max - param_min) * 0.05,
        ]

    # 共通の軸設定を取得（日付変換最適化）
    axis_config = get_shared_axis_config()

    # 開始時間を数値化
    time_begin_numeric = matplotlib.dates.date2num(time_begin)

    # サブプロットを一括生成（最適化）
    num_rows = len(panel_config["param_list"])
    num_cols = len(room_list)

    # 既存のfigを使って、gridspecでサブプロットを作成
    gs = matplotlib.gridspec.GridSpec(
        num_rows, num_cols, figure=fig, hspace=0.1, wspace=0, left=0.05, bottom=0.08, right=0.98, top=0.92
    )
    axes = []
    for i in range(num_rows * num_cols):
        row = i // num_cols
        col = i % num_cols
        ax = fig.add_subplot(gs[row, col])
        axes.append(ax)

    # axesはすでにリストとして作成済み

    for row, param in enumerate(panel_config["param_list"]):
        logging.info("draw %s graph", param["name"])

        for col in range(len(room_list)):
            # キャッシュからデータを取得（最適化）
            data = data_cache[param["name"]][col]
            if not data["valid"]:
                data = cache

            # 一括生成したaxesを使用
            ax_index = row * num_cols + col
            ax = axes[ax_index]

            title = room_list[col]["label"] if row == 0 else None
            graph_range = range_map[param["name"]] if param["range"] == "auto" else param["range"]

            plot_item(
                ax,
                title,
                param["unit"],
                data,
                time_begin_numeric,
                graph_range,
                param["format"],
                param["scale"],
                param["size_small"],
                face_map,
                axis_config,
            )

            if (param["name"] == "temp") and ("aircon" in room_list[col]):
                draw_aircon_icon(
                    ax,
                    get_aircon_power_from_results(aircon_results, aircon_map, col),
                    panel_config["icon"],
                )

            if (param["name"] == "lux") and room_list[col]["light_icon"]:
                draw_light_icon(ax, data["value"], panel_config["icon"])

    # サブプロット一括生成時にgridspec_kwで設定済みのため、追加のレイアウト調整は不要

    buf = io.BytesIO()
    matplotlib.pyplot.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    buf.seek(0)

    img = PIL.Image.open(buf).copy()

    buf.close()

    matplotlib.pyplot.clf()
    matplotlib.pyplot.close(fig)

    return img


def create(config):
    logging.info("draw sensor graph")
    start = time.perf_counter()

    panel_config = config["sensor"]
    font_config = config["font"]
    db_config = config["influxdb"]

    try:
        return (
            create_sensor_graph_impl(panel_config, font_config, db_config),
            time.perf_counter() - start,
        )
    except Exception:
        error_message = traceback.format_exc()
        return (
            my_lib.panel_util.create_error_image(panel_config, font_config, error_message),
            time.perf_counter() - start,
            error_message,
        )


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    out_file = args["-o"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    result = create(config)

    if len(result) > 2:
        # エラーが発生した場合
        img, elapsed_time, error_message = result
        logging.error("Error occurred: %s", error_message)
        logging.info("Elapsed time: %.2f seconds", elapsed_time)
    else:
        # 正常な場合
        img, elapsed_time = result
        logging.info("Elapsed time: %.2f seconds", elapsed_time)

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
