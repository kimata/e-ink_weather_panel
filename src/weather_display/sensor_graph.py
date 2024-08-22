#!/usr/bin/env python3
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

import matplotlib as mpl
import matplotlib.dates as mdates
import matplotlib.font_manager
import matplotlib.pyplot as plt
import my_lib.panel_util
import PIL.Image
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from my_lib.sensor_data import fetch_data
from pandas.plotting import register_matplotlib_converters

mpl.use("Agg")

register_matplotlib_converters()

IMAGE_DPI = 100.0
EMPTY_VALUE = -100.0

AIRCON_WORK_THRESHOLD = 30


def get_plot_font(config, font_type, size):
    font_path = str(pathlib.Path(config["path"]) / config["map"][font_type])

    logging.info("Load font: %s", font_path)

    return matplotlib.font_manager.FontProperties(fname=font_path, size=size)


def get_face_map(font_config):
    return {
        "title": get_plot_font(font_config, "jp_bold", 34),
        "value": get_plot_font(font_config, "en_cond", 65),
        "value_small": get_plot_font(font_config, "en_cond", 55),
        "value_unit": get_plot_font(font_config, "jp_regular", 18),
        "yaxis": get_plot_font(font_config, "jp_regular", 20),
        "xaxis": get_plot_font(font_config, "en_medium", 20),
    }


def plot_item(ax, title, unit, data, xbegin, ylim, fmt, scale, small, face_map):  # noqa: PLR0913
    logging.info("Plot %s", title)

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

    font = face_map["value_small"] if small else face_map["value"]

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
        aircon["measure"],
        aircon["host"],
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

    icon_file = icon_config["aircon"]["path"]

    img = plt.imread(str(pathlib.Path(icon_file)))

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

    img = plt.imread(str(pathlib.Path(icon_file)))

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
            host_specify["type"],
            host_specify["name"],
            param,
            period_start,
            period_stop,
        )
        if data["valid"]:
            return data
    return data


def create_sensor_graph_impl(panel_config, font_config, db_config):  # noqa: C901
    face_map = get_face_map(font_config)

    room_list = panel_config["room_list"]
    width = panel_config["panel"]["width"]
    height = panel_config["panel"]["height"]

    plt.style.use("grayscale")

    fig = plt.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    cache = None
    range_map = {}
    time_begin = datetime.datetime.now(datetime.timezone.utc)
    for param in panel_config["param_list"]:
        logging.info("fetch %s data", param["name"])

        param_min = float("inf")
        param_max = -float("inf")

        for col in range(len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]["host"],
                param["name"],
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
        range_map[param["name"]] = [
            max(0, param_min - (param_max - param_min) * 0.3),
            param_max + (param_max - param_min) * 0.05,
        ]

    for row, param in enumerate(panel_config["param_list"]):
        logging.info("draw %s graph", param["name"])

        for col in range(len(room_list)):
            data = sensor_data(
                db_config,
                room_list[col]["host"],
                param["name"],
            )
            if not data["valid"]:
                data = cache

            ax = fig.add_subplot(
                len(panel_config["param_list"]),
                len(room_list),
                1 + len(room_list) * row + col,
            )

            title = room_list[col]["label"] if row == 0 else None
            graph_range = range_map[param["name"]] if param["range"] == "auto" else param["range"]

            plot_item(
                ax,
                title,
                param["unit"],
                data,
                time_begin,
                graph_range,
                param["format"],
                param["scale"],
                param["size_small"],
                face_map,
            )

            if (param["name"] == "temp") and ("aircon" in room_list[col]):
                draw_aircon_icon(
                    ax,
                    get_aircon_power(db_config, room_list[col]["aircon"]),
                    panel_config["icon"],
                )

            if (param["name"] == "lux") and room_list[col]["light_icon"]:
                draw_light_icon(ax, data["value"], panel_config["icon"])

    fig.tight_layout()
    plt.subplots_adjust(hspace=0.1, wspace=0)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    return PIL.Image.open(buf)


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
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    out_file = args["-o"]

    img = create(config)[0]

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
