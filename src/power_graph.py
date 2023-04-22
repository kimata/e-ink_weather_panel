#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib
import os
import datetime
import io
import matplotlib
import PIL.Image
import logging

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()
from matplotlib.font_manager import FontProperties

from sensor_data import fetch_data

IMAGE_DPI = 100.0


def get_plot_font(config, font_type, size):
    return FontProperties(
        fname=str(
            pathlib.Path(
                os.path.dirname(__file__), config["PATH"], config["MAP"][font_type]
            )
        ),
        size=size,
    )


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "JP_BOLD", 60),
        "value": get_plot_font(font_config, "EN_COND_BOLD", 80),
        "value_unit": get_plot_font(font_config, "JP_REGULAR", 18),
        "axis_minor": get_plot_font(font_config, "JP_REGULAR", 30),
        "axis_major": get_plot_font(font_config, "JP_REGULAR", 40),
    }


def plot_item(ax, title, unit, data, ylabel, ylim, fmt, face_map):
    x = data["time"]
    y = data["value"]

    if title is not None:
        ax.set_title(title, fontproperties=face_map["title"], color="#333333")
    ax.set_ylim(ylim)
    ax.set_xlim([x[0], x[-1] + datetime.timedelta(minutes=15)])

    ax.plot(
        x,
        y,
        color="#CCCCCC",
        marker="o",
        markevery=[len(y) - 1],
        markersize=5,
        markerfacecolor="#DDDDDD",
        markeredgewidth=3,
        markeredgecolor="#666666",
        linewidth=3.0,
        linestyle="solid",
    )

    ax.fill_between(x, y, 0, facecolor="#DDDDDD", alpha=0.5)

    if not data["valid"]:
        text = "?"
    else:
        text = fmt.format(next((item for item in reversed(y) if item), None))

    ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 6)))
    ax.xaxis.set_minor_formatter(mdates.DateFormatter("\n%-H"))
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
        alpha=1.0,
        fontproperties=face_map["value"],
    )

    ax.text(
        1,
        0.05,
        unit,
        transform=ax.transAxes,
        horizontalalignment="right",
        color="#000000",
        alpha=1.0,
        fontproperties=face_map["value_unit"],
    )

    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["left"].set_visible(False)

    ax.label_outer()


def create_power_graph(config):
    logging.info("draw power graph")

    db_config = config["INFLUXDB"]
    panel_config = config["POWER"]
    font_config = config["FONT"]

    face_map = get_face_map(font_config)

    width = panel_config["GRAPH"]["WIDTH"]
    height = panel_config["GRAPH"]["HEIGHT"]

    plt.style.use("grayscale")

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    data = fetch_data(
        db_config,
        panel_config["DATA"]["HOST"]["TYPE"],
        panel_config["DATA"]["HOST"]["NAME"],
        panel_config["DATA"]["PARAM"]["NAME"],
    )

    ax = fig.add_subplot()
    plot_item(
        ax,
        None,
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
    plt.savefig(buf, format="png", dpi=IMAGE_DPI)

    return PIL.Image.open(buf)
