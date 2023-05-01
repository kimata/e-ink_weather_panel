#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import textwrap
import PIL.Image
import os
import pathlib
import logging
from concurrent import futures
import logger

from weather_panel import create_weather_panel, get_font, draw_text
from power_graph import create_power_graph
from sensor_graph import create_sensor_graph
from rain_cloud_panel import create_rain_cloud_panel
from time_panel import create_time_panel

from config import load_config


def alpha_paste(img, paint_img, pos, overlay):
    canvas = overlay.copy()
    canvas.paste(paint_img, pos)
    img.alpha_composite(canvas, (0, 0))


def draw_wall(config, img, overlay):
    for wall_config in config["WALL"]:
        mascot = PIL.Image.open(
            str(pathlib.Path(os.path.dirname(__file__), wall_config["IMAGE"]))
        )

        if "RESIZE" in wall_config:
            mascot = mascot.resize(
                (
                    int(mascot.size[0] * wall_config["SCALE"]),
                    int(mascot.size[1] * wall_config["SCALE"]),
                )
            )
        if "BRIGHTNESS" in wall_config:
            mascot = PIL.ImageEnhance.Brightness(mascot).enhance(
                wall_config["BRIGHTNESS"]
            )

        alpha_paste(
            img,
            mascot,
            (wall_config["OFFSET_X"], wall_config["OFFSET_Y"]),
            overlay,
        )


def draw_panel(config, img):
    overlay = PIL.Image.new(
        "RGBA",
        (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        (255, 255, 255, 0),
    )
    panel_map = {
        "weather": {"func": create_weather_panel},
        "sensor": {"func": create_sensor_graph},
        "rain_cloud": {"func": create_rain_cloud_panel},
        "time": {"func": create_time_panel},
    }

    # NOTE: マルチスレッド処理
    with futures.ThreadPoolExecutor() as executor:
        for name in panel_map.keys():
            panel_map[name]["task"] = executor.submit(panel_map[name]["func"], config)

    # NOTE: matplotlib はスレッドセーフではないので，別スレッドで処理しない
    power_graph_img = create_power_graph(config)

    draw_wall(config, img, overlay)

    alpha_paste(
        img,
        power_graph_img,
        (
            0,
            config["WEATHER"]["PANEL"]["HEIGHT"] - config["POWER"]["PANEL"]["OVERLAP"],
        ),
        overlay,
    )

    img.alpha_composite(panel_map["weather"]["task"].result(), (0, 0))
    alpha_paste(
        img,
        panel_map["sensor"]["task"].result(),
        (
            0,
            config["WEATHER"]["PANEL"]["HEIGHT"]
            + config["POWER"]["PANEL"]["HEIGHT"]
            - config["POWER"]["PANEL"]["OVERLAP"]
            - config["SENSOR"]["PANEL"]["OVERLAP"],
        ),
        overlay,
    )
    alpha_paste(
        img,
        panel_map["rain_cloud"]["task"].result(),
        (
            config["RAIN_CLOUD"]["PANEL"]["OFFSET_X"],
            config["RAIN_CLOUD"]["PANEL"]["OFFSET_Y"],
        ),
        overlay,
    )
    alpha_paste(
        img,
        panel_map["time"]["task"].result(),
        (0, 0),
        overlay,
    )


######################################################################
logger.init("panel.e-ink.weather")

logging.info("start to create image")

config = load_config()

img = PIL.Image.new(
    "RGBA",
    (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
    (255, 255, 255, 255),
)

try:
    draw_panel(config, img)
except:
    import traceback

    draw = PIL.ImageDraw.Draw(img)
    draw.rectangle(
        (0, 0, config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        fill=(255, 255, 255, 255),
    )

    draw_text(
        img,
        "ERROR",
        [10, 10],
        get_font(config["FONT"], "EN_BOLD", 160),
        "left",
        "#666",
    )

    draw_text(
        img,
        "\n".join(textwrap.wrap(traceback.format_exc(), 100)),
        [20, 200],
        get_font(config["FONT"], "EN_MEDIUM", 40),
        "left" "#333",
    )
    print(traceback.format_exc(), file=sys.stderr)

img.save(sys.stdout.buffer, "PNG")

exit(0)
