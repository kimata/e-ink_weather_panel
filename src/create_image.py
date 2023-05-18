#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を生成します．

Usage:
  create_image.py [-f CONFIG] [-o PNG_FILE]

Options:
  -f CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

from docopt import docopt

import sys
import PIL.Image
import time
import logging

# from concurrent import futures
import multiprocessing
import logger
import traceback
import textwrap
import notify_slack

from pil_util import get_font, draw_text, load_image, alpha_paste, convert_to_gray
from weather_panel import create_weather_panel
from power_graph import create_power_graph
from sensor_graph import create_sensor_graph
from rain_cloud_panel import create_rain_cloud_panel
from time_panel import create_time_panel

from config import load_config


def draw_wall(config, img):
    for wall_config in config["WALL"]["IMAGE"]:
        alpha_paste(
            img,
            load_image(wall_config),
            (wall_config["OFFSET_X"], wall_config["OFFSET_Y"]),
        )


def draw_panel(config, img):
    panel_list = [
        {"name": "rain_cloud", "func": create_rain_cloud_panel},
        {"name": "sensor", "func": create_sensor_graph},
        {"name": "power", "func": create_power_graph},
        {"name": "weather", "func": create_weather_panel},
        {"name": "time", "func": create_time_panel},
    ]

    panel_map = {}

    # NOTE: 並列処理 (matplotlib はマルチスレッド対応していないので，マルチプロセス処理する)
    start = time.perf_counter()
    pool = multiprocessing.Pool(processes=len(panel_list))
    for panel in panel_list:
        panel["task"] = pool.apply_async(panel["func"], (config,))
    pool.close()
    pool.join()

    for panel in panel_list:
        result = panel["task"].get()
        panel_map[panel["name"]] = result[0]
        logging.info(
            "elapsed time: {name} panel = {time:.3f} sec".format(
                name=panel["name"], time=result[1]
            )
        )
    logging.info(
        "total elapsed time: {time:.3f} sec".format(time=time.perf_counter() - start)
    )

    draw_wall(config, img)

    alpha_paste(
        img,
        panel_map["power"],
        (
            0,
            config["WEATHER"]["PANEL"]["HEIGHT"] - config["POWER"]["PANEL"]["OVERLAP"],
        ),
    )

    img.alpha_composite(panel_map["weather"], (0, 0))
    alpha_paste(
        img,
        panel_map["sensor"],
        (
            0,
            config["WEATHER"]["PANEL"]["HEIGHT"]
            + config["POWER"]["PANEL"]["HEIGHT"]
            - config["POWER"]["PANEL"]["OVERLAP"]
            - config["SENSOR"]["PANEL"]["OVERLAP"],
        ),
    )
    alpha_paste(
        img,
        panel_map["rain_cloud"],
        (
            config["RAIN_CLOUD"]["PANEL"]["OFFSET_X"],
            config["RAIN_CLOUD"]["PANEL"]["OFFSET_Y"],
        ),
    )
    alpha_paste(
        img,
        panel_map["time"],
        (0, 0),
    )


######################################################################
args = docopt(__doc__)

logger.init("panel.e-ink.weather", level=logging.INFO)

logging.info("start to create image")

config = load_config(args["-f"])

img = PIL.Image.new(
    "RGBA",
    (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
    (255, 255, 255, 255),
)

status = 0
try:
    draw_panel(config, img)
except:
    draw = PIL.ImageDraw.Draw(img)
    draw.rectangle(
        (0, 0, config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        fill=(255, 255, 255, 255),
    )

    draw_text(
        img,
        "ERROR",
        (10, 10),
        get_font(config["FONT"], "EN_BOLD", 160),
        "left",
        "#666",
    )

    draw_text(
        img,
        "\n".join(textwrap.wrap(traceback.format_exc(), 100)),
        (20, 200),
        get_font(config["FONT"], "EN_MEDIUM", 40),
        "left" "#333",
    )
    if "SLACK" in config:
        notify_slack.error(
            config["SLACK"]["BOT_TOKEN"],
            config["SLACK"]["ERROR"]["CHANNEL"]["NAME"],
            traceback.format_exc(),
            interval_min=config["SLACK"]["ERROR"]["INTERVAL_MIN"],
        )
    print(traceback.format_exc(), file=sys.stderr)
    # NOTE: 使われてなさそうな値にしておく．
    # display_image.py と合わせる必要あり．
    status = 222

if args["-o"] is not None:
    out_file = args["-o"]
else:
    out_file = sys.stdout.buffer

logging.info("Save {out_file}.".format(out_file=str(out_file)))
convert_to_gray(img).save(out_file, "PNG")

exit(status)
