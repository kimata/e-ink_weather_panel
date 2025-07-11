#!/usr/bin/env python3
"""
消費電力グラフを生成します。

Usage:
  power_graph.py [-c CONFIG] -o PNG_FILE [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o PNG_FILE       : 生成した画像を指定されたパスに保存します。
  -D                : デバッグモードで動作します。
"""

import datetime
import functools
import io
import logging
import os
import pathlib
import time
import traceback

import matplotlib  # noqa: ICN001
import my_lib.notify.slack
import PIL.Image

matplotlib.use("Agg")

import matplotlib.dates
import matplotlib.font_manager
import matplotlib.pyplot  # noqa: ICN001
import my_lib.panel_util
import pandas.plotting
from my_lib.sensor_data import fetch_data

pandas.plotting.register_matplotlib_converters()

IMAGE_DPI = 100.0


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
        "title": get_plot_font(font_config, "jp_bold", 60),
        "value": get_plot_font(font_config, "en_cond_bold", 80),
        "value_unit": get_plot_font(font_config, "jp_regular", 18),
        "axis_minor": get_plot_font(font_config, "jp_regular", 26),
        "axis_major": get_plot_font(font_config, "jp_regular", 32),
    }


def plot_item(ax, unit, data, ylim, fmt, face_map):  # noqa: PLR0913
    x = data["time"]
    y = data["value"]

    # デバッグログ: データの状態を確認
    logging.info(
        "plot_item debug: x length=%d, y length=%d, data_valid=%s",
        len(x),
        len(y),
        data.get("valid", "unknown"),
    )

    # 空リストチェック
    if not x or not y:
        logging.warning("Empty data detected in plot_item: x=%d, y=%d", len(x), len(y))
        # 空データの場合は何も描画せずに戻る
        ax.text(
            0.5,
            0.5,
            "No Data Available",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=12,
            color="red",
        )
        # 空データエラーをSlackに通知
        error_msg = f"Empty data in power_graph: x={len(x)}, y={len(y)}"
        raise ValueError(error_msg)

    if len(x) != len(y):
        logging.error("Mismatched data lengths: x=%d, y=%d", len(x), len(y))
        return

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

    ax.xaxis.set_minor_locator(matplotlib.dates.HourLocator(byhour=range(0, 24, 6)))
    ax.xaxis.set_minor_formatter(matplotlib.dates.DateFormatter("%-H"))
    ax.xaxis.set_major_locator(matplotlib.dates.DayLocator(interval=1))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%-d日"))

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

    matplotlib.pyplot.style.use("grayscale")

    fig = matplotlib.pyplot.figure(facecolor="azure", edgecolor="coral", linewidth=2)

    fig.set_size_inches(width / IMAGE_DPI, height / IMAGE_DPI)

    if os.environ.get("DUMMY_MODE", "false") == "true":
        period_start = "-228h"
        period_stop = "-168h"
    else:
        period_start = "-60h"
        period_stop = "now()"

    # デバッグログ: fetch_data呼び出し前
    logging.info(
        "Fetching power data: measure=%s, hostname=%s, field=%s, period=%s to %s",
        panel_config["data"]["sensor"]["measure"],
        panel_config["data"]["sensor"]["hostname"],
        panel_config["data"]["param"]["field"],
        period_start,
        period_stop,
    )

    data = fetch_data(
        db_config,
        panel_config["data"]["sensor"]["measure"],
        panel_config["data"]["sensor"]["hostname"],
        panel_config["data"]["param"]["field"],
        period_start,
        period_stop,
    )

    # デバッグログ: fetch_data結果
    logging.info(
        "Power data fetched: valid=%s, time_length=%d, value_length=%d",
        data.get("valid", False),
        len(data.get("time", [])),
        len(data.get("value", [])),
    )

    # データが無効な場合の詳細ログ
    if not data.get("valid", False) or not data.get("time", []) or not data.get("value", []):
        logging.warning("Invalid or empty power data: %s", data)
        if not data.get("time", []):
            logging.warning("time data is empty")
        if not data.get("value", []):
            logging.warning("value data is empty")

    ax = fig.add_subplot()
    plot_item(
        ax,
        panel_config["data"]["param"]["unit"],
        data,
        panel_config["data"]["param"]["range"],
        panel_config["data"]["param"]["format"],
        face_map,
    )

    matplotlib.pyplot.subplots_adjust(hspace=0, wspace=0)
    fig.tight_layout()

    buf = io.BytesIO()
    matplotlib.pyplot.savefig(buf, format="png", dpi=IMAGE_DPI, transparent=True)

    buf.seek(0)

    img = PIL.Image.open(buf).copy()

    buf.close()

    matplotlib.pyplot.clf()
    matplotlib.pyplot.close(fig)

    return img


def create(config):
    logging.info("draw power graph")

    start = time.perf_counter()

    panel_config = config["power"]
    font_config = config["font"]
    db_config = config["influxdb"]
    slack_config = config.get("slack")

    try:
        return (
            create_power_graph_impl(panel_config, font_config, db_config),
            time.perf_counter() - start,
        )
    except Exception as e:
        error_message = traceback.format_exc()

        # 空データエラーの場合はSlack通知
        if "Empty data in power_graph" in str(e) and slack_config is not None:
            try:
                slack_message = f"Power Graph Data Error: {e!s}\n\n詳細:\n{error_message}"
                my_lib.notify.slack.error(
                    slack_config["bot_token"],
                    slack_config["error"]["channel"]["name"],
                    slack_config["error"]["channel"]["id"],
                    slack_config["from"],
                    slack_message,
                    interval_min=slack_config["error"]["interval_min"],
                )
                logging.info("Sent Slack notification for empty power data")
            except Exception as slack_error:
                logging.warning("Failed to send Slack notification: %s", slack_error)

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
    import my_lib.pil_util

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
