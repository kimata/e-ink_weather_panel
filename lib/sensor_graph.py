#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
センサーグラフを生成します．

Usage:
  sensor_graph.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

import datetime
import io
import logging
import os
import pathlib
import time
import traceback

import matplotlib
import PIL.Image

matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
from config import get_db_config
from matplotlib.font_manager import FontProperties
from panel_util import error_image
from sensor_data import fetch_data

IMAGE_DPI = 100.0
EMPTY_VALUE = -100.0

AIRCON_WORK_THRESHOLD = 30


def get_plot_font(config, font_type, size):
    font_path = str(pathlib.Path(os.path.dirname(__file__), config["PATH"], config["MAP"][font_type]))

    logging.info("Load font: {path}".format(path=font_path))

    return FontProperties(fname=font_path, size=size)


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "JP_BOLD", 34),
        "value": get_plot_font(font_config, "EN_COND", 65),
        "value_small": get_plot_font(font_config, "EN_COND", 55),
        "value_unit": get_plot_font(font_config, "JP_REGULAR", 18),
        "yaxis": get_plot_font(font_config, "JP_REGULAR", 20),
        "xaxis": get_plot_font(font_config, "EN_MEDIUM", 20),
    }


def plot_item(ax, title, unit, data, xbegin, ylabel, ylim, fmt, scale, small, face_map):
    logging.info("Plot {title}".format(title=title))

    x = data["time"]
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
    ax.set_xlim([xbegin, x[-1] + datetime.timedelta(hours=3)])

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

    if small:
        font = face_map["value_small"]
    else:
        font = face_map["value"]

    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d"))
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


def get_aircon_power(db_config, aircon):
    if os.environ.get("DUMMY_MODE", "false") == "true":
        start = "-169h"
        stop = "-168h"
    else:
        start = "-1h"
        stop = "now()"

    data = fetch_data(
        db_config,
        aircon["MEASURE"],
        aircon["HOST"],
        "power",
        start,
        stop,
        last=True,
    )

    if data["valid"]:
        return data["value"][0]
    else:
        return None


def draw_aircon_icon(ax, power, icon_config):
    if (power is None) or (power < AIRCON_WORK_THRESHOLD):
        return

    icon_file = icon_config["AIRCON"]["PATH"]

    img = plt.imread(str(pathlib.Path(os.path.dirname(__file__), icon_file)))

    imagebox = OffsetImage(img, zoom=0.3)
    imagebox.image.axes = ax

    ab = AnnotationBbox(
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

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9)))
    # NOTE: 昼間はアイコンを描画しない
    if (now.hour > 7) and (now.hour < 17):
        return

    if lux == EMPTY_VALUE:
        return
    elif lux < 10:
        icon_file = icon_config["LIGHT"]["OFF"]["PATH"]
    else:
        icon_file = icon_config["LIGHT"]["ON"]["PATH"]

    img = plt.imread(str(pathlib.Path(os.path.dirname(__file__), icon_file)))

    imagebox = OffsetImage(img, zoom=0.25)
    imagebox.image.axes = ax

    ab = AnnotationBbox(
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
            host_specify["TYPE"],
            host_specify["NAME"],
            param,
            period_start,
            period_stop,
        )
        if data["valid"]:
            return data
    return data


def create_sensor_graph_impl(panel_config, font_config, db_config):
    face_map = get_face_map(font_config)

    room_list = panel_config["ROOM_LIST"]
    width = panel_config["PANEL"]["WIDTH"]
    height = panel_config["PANEL"]["HEIGHT"]

    plt.style.use("grayscale")

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    cache = None
    range_map = {}
    time_begin = datetime.datetime.now(datetime.timezone.utc)
    for row, param in enumerate(panel_config["PARAM_LIST"]):
        logging.info("fetch {name} data".format(name=param["NAME"]))

        param_min = float("inf")
        param_max = -float("inf")

        for col in range(0, len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]["HOST"],
                param["NAME"],
            )
            if not data["valid"]:
                continue
            if data["time"][0] < time_begin:
                time_begin = data["time"][0]
            if cache is None:
                cache = {
                    "time": data["time"],
                    "value": [EMPTY_VALUE for x in range(len(data["time"]))],
                    "valid": False,
                }

            min_val = min([item for item in data["value"] if item is not None])
            max_val = max([item for item in data["value"] if item is not None])
            if min_val < param_min:
                param_min = min_val
            if max_val > param_max:
                param_max = max_val

        # NOTE: 見やすくなるように，ちょっと広げる
        range_map[param["NAME"]] = [
            max(0, param_min - (param_max - param_min) * 0.3),
            param_max + (param_max - param_min) * 0.05,
        ]

    for row, param in enumerate(panel_config["PARAM_LIST"]):
        logging.info("draw {name} graph".format(name=param["NAME"]))

        for col in range(0, len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]["HOST"],
                param["NAME"],
            )
            if not data["valid"]:
                data = cache

            ax = fig.add_subplot(
                len(panel_config["PARAM_LIST"]),
                len(room_list),
                1 + len(room_list) * row + col,
            )

            if row == 0:
                title = room_list[col]["LABEL"]
            else:
                title = None

            if param["RANGE"] == "auto":
                graph_range = range_map[param["NAME"]]
            else:
                graph_range = param["RANGE"]

            plot_item(
                ax,
                title,
                param["UNIT"],
                data,
                time_begin,
                param["UNIT"],
                graph_range,
                param["FORMAT"],
                param["SCALE"],
                param["SIZE_SMALL"],
                face_map,
            )

            if param["NAME"] == "temp":
                if "AIRCON" in room_list[col]:
                    draw_aircon_icon(
                        ax,
                        get_aircon_power(db_config, room_list[col]["AIRCON"]),
                        panel_config["ICON"],
                    )

            if param["NAME"] == "lux":
                if room_list[col]["LIGHT_ICON"]:
                    draw_light_icon(ax, data["value"], panel_config["ICON"])

    fig.tight_layout()
    plt.subplots_adjust(hspace=0.1, wspace=0)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    return PIL.Image.open(buf)


def create_sensor_graph(config):
    logging.info("draw sensor graph")
    start = time.perf_counter()

    panel_config = config["SENSOR"]
    font_config = config["FONT"]
    db_config = get_db_config(config)

    try:
        return (
            create_sensor_graph_impl(panel_config, font_config, db_config),
            time.perf_counter() - start,
        )
    except:
        error_message = traceback.format_exc()
        return (
            error_image(panel_config, font_config, error_message),
            time.perf_counter() - start,
            error_message,
        )


if __name__ == "__main__":
    import logger
    from config import load_config
    from docopt import docopt
    from pil_util import convert_to_gray

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])
    out_file = args["-o"]

    img = create_sensor_graph(config)[0]

    logging.info("Save {out_file}.".format(out_file=out_file))
    convert_to_gray(img).save(out_file, "PNG")

    print("Finish.")
