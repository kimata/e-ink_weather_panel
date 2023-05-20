#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import os
import time
import datetime
import io
import matplotlib
import PIL.Image
import logging

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
from matplotlib.font_manager import FontProperties

from sensor_data import fetch_data

IMAGE_DPI = 100.0
EMPTY_VALUE = -100.0


def get_plot_font(config, font_type, size):
    font_path = str(
        pathlib.Path(
            os.path.dirname(__file__), config["PATH"], config["MAP"][font_type]
        )
    )

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
        text = fmt.format(
            next((item for item in reversed(y) if item is not None), None)
        )

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


def draw_light_icon(config, ax, y):
    lux = next((item for item in reversed(y) if item is not None), None)

    now = datetime.datetime.now()
    # NOTE: 昼間はアイコンを描画しない
    if (now.hour > 7) and (now.hour < 17):
        return

    if lux == EMPTY_VALUE:
        return
    elif lux < 10:
        icon_file = config["LIGHT"]["OFF"]["PATH"]
    else:
        icon_file = config["LIGHT"]["ON"]["PATH"]

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


def sensor_data(config, host_specify_list, param, period="60h"):
    for host_specify in host_specify_list:
        data = fetch_data(
            config, host_specify["TYPE"], host_specify["NAME"], param, period
        )
        if data["valid"]:
            return data
    return data


def create_sensor_graph(config):
    logging.info("draw sensor graph")
    start = time.perf_counter()

    face_map = get_face_map(config["FONT"])

    room_list = config["SENSOR"]["ROOM_LIST"]
    width = config["SENSOR"]["PANEL"]["WIDTH"]
    height = config["SENSOR"]["PANEL"]["HEIGHT"]

    plt.style.use("grayscale")

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    cache = None
    range_map = {}
    time_begin = datetime.datetime.now(datetime.timezone.utc)
    for row, param in enumerate(config["SENSOR"]["PARAM_LIST"]):
        logging.info("fetch {name} data".format(name=param["NAME"]))

        param_min = float("inf")
        param_max = -float("inf")

        for col in range(0, len(room_list)):
            data = sensor_data(
                config["INFLUXDB"],
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
            if len(data["value"]) == 0:
                continue

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

    for row, param in enumerate(config["SENSOR"]["PARAM_LIST"]):
        logging.info("draw {name} graph".format(name=param["NAME"]))

        for col in range(0, len(room_list)):
            data = sensor_data(
                config["INFLUXDB"],
                room_list[col]["HOST"],
                param["NAME"],
            )
            if not data["valid"]:
                data = cache

            ax = fig.add_subplot(
                len(config["SENSOR"]["PARAM_LIST"]),
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

            if param["NAME"] == "lux":
                if room_list[col]["ICON"]:
                    draw_light_icon(config["SENSOR"]["ICON"], ax, data["value"])

    fig.tight_layout()
    plt.subplots_adjust(hspace=0.1, wspace=0)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    return (PIL.Image.open(buf), time.perf_counter() - start)
