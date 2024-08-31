#!/usr/bin/env python3
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

import matplotlib as mpl
import PIL.Image

mpl.use("Agg")

import matplotlib.dates as mdates
import matplotlib.font_manager
import matplotlib.pyplot as plt
import my_lib.panel_util
from my_lib.sensor_data import fetch_data
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()

IMAGE_DPI = 100.0


def get_plot_font(config, font_type, size):
    font_path = pathlib.Path(config["path"]).resolve() / config["map"][font_type]

    logging.info("Load font: %s", font_path)

    return mpl.font_manager.FontProperties(fname=font_path, size=size)


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "jp_bold", 60),
        "value": get_plot_font(font_config, "en_cond_bold", 80),
        "value_unit": get_plot_font(font_config, "jp_regular", 18),
        "axis_minor": get_plot_font(font_config, "jp_regular", 26),
        "axis_major": get_plot_font(font_config, "jp_regular", 32),
    }


def plot_item(ax, unit, data, ylim, fmt, face_map):  # noqa: PLR0913
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

    text = "?" if not data["valid"] else fmt.format(next((item for item in reversed(y) if item), None))

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

    width = panel_config["panel"]["width"]
    height = panel_config["panel"]["height"]

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
        panel_config["data"]["host"]["type"],
        panel_config["data"]["host"]["name"],
        panel_config["data"]["param"]["name"],
        period_start,
        period_stop,
    )

    ax = fig.add_subplot()
    plot_item(
        ax,
        panel_config["data"]["param"]["unit"],
        data,
        panel_config["data"]["param"]["range"],
        panel_config["data"]["param"]["format"],
        face_map,
    )

    plt.subplots_adjust(hspace=0, wspace=0)
    fig.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    buf.seek(0)

    img = PIL.Image.open(buf).copy()

    buf.close()

    plt.clf()
    plt.close(fig)

    return img


def create(config):
    logging.info("draw power graph")

    start = time.perf_counter()

    panel_config = config["power"]
    font_config = config["font"]
    db_config = config["influxdb"]

    try:
        return (
            create_power_graph_impl(panel_config, font_config, db_config),
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
    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pil_util

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    out_file = args["-o"]

    img = create(config)[0]

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
