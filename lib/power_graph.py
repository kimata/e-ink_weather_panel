#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消費電力グラフを生成します．

Usage:
  power_graph.py [-c CONFIG] -o PNG_FILE

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
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
from config import get_db_config
from matplotlib.font_manager import FontProperties
from panel_util import error_image
from sensor_data import fetch_data

IMAGE_DPI = 100.0


def get_plot_font(config, font_type, size):
    return FontProperties(
        fname=str(pathlib.Path(os.path.dirname(__file__), config["PATH"], config["MAP"][font_type])),
        size=size,
    )


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "JP_BOLD", 60),
        "value": get_plot_font(font_config, "EN_COND_BOLD", 80),
        "value_unit": get_plot_font(font_config, "JP_REGULAR", 18),
        "axis_minor": get_plot_font(font_config, "JP_REGULAR", 26),
        "axis_major": get_plot_font(font_config, "JP_REGULAR", 32),
    }


def plot_item(ax, unit, data, ylabel, ylim, fmt, face_map):
    x = data["time"]
    y = data["value"]

    ax.set_ylim(ylim)
    ax.set_xlim([x[0], x[-1] + datetime.timedelta(minutes=15)])

    ax.plot(
        x,
        y,
        color="#CCCCCC",
        marker="o",
        markevery=[len(y) - 1],
        markersize=8,
        markerfacecolor="#999999",
        markeredgewidth=3,
        markeredgecolor="#666666",
        linewidth=3.0,
        linestyle="solid",
    )

    ax.fill_between(x, y, 0, facecolor="#D0D0D0", alpha=0.5)

    if not data["valid"]:
        text = "?"
    else:
        text = fmt.format(next((item for item in reversed(y) if item), None))

    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter("%-H"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-d日"))

    for label in ax.get_xticklabels():
        label.set_fontproperties(face_map["axis_major"])
    for label in ax.get_xminorticklabels():
        label.set_fontproperties(face_map["axis_minor"])

    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4))
    ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("{x:,.0f}"))

    ax.grid(axis="x", color="#000000", alpha=0.1, linestyle="-", linewidth=1)

    ax.text(
        0.977,
        0.05,
        text,
        transform=ax.transAxes,
        horizontalalignment="right",
        color="#000000",
        alpha=0.8,
        fontproperties=face_map["value"],
    )

    ax.text(
        1,
        0.05,
        unit,
        transform=ax.transAxes,
        horizontalalignment="right",
        color="#000000",
        alpha=0.8,
        fontproperties=face_map["value_unit"],
    )

    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)

    ax.label_outer()


def create_power_graph_impl(panel_config, font_config, db_config):
    face_map = get_face_map(font_config)

    width = panel_config["PANEL"]["WIDTH"]
    height = panel_config["PANEL"]["HEIGHT"]

    plt.style.use("grayscale")

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    if os.environ.get("DUMMY_MODE", "false") == "true":
        period_start = "-228h"
        period_stop = "-168h"
    else:
        period_start = "-60h"
        period_stop = "now()"

    data = fetch_data(
        db_config,
        panel_config["DATA"]["HOST"]["TYPE"],
        panel_config["DATA"]["HOST"]["NAME"],
        panel_config["DATA"]["PARAM"]["NAME"],
        period_start,
        period_stop,
    )

    ax = fig.add_subplot()
    plot_item(
        ax,
        panel_config["DATA"]["PARAM"]["UNIT"],
        data,
        panel_config["DATA"]["PARAM"]["UNIT"],
        panel_config["DATA"]["PARAM"]["RANGE"],
        panel_config["DATA"]["PARAM"]["FORMAT"],
        face_map,
    )

    plt.subplots_adjust(hspace=0, wspace=0)
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    return PIL.Image.open(buf)


def create(config):
    logging.info("draw power graph")

    start = time.perf_counter()

    panel_config = config["POWER"]
    font_config = config["FONT"]
    db_config = get_db_config(config)

    try:
        return (
            create_power_graph_impl(panel_config, font_config, db_config),
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

    img = create(config)[0]

    logging.info("Save {out_file}.".format(out_file=out_file))
    convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
