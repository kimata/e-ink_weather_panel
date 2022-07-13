#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import sys
import os
import textwrap
import pathlib
import PIL.Image

from weather_panel import create_weather_panel, get_font, draw_text
from power_graph import create_power_graph
from sensor_graph import create_sensor_graph


CONFIG_PATH = "../config.yml"


def load_config():
    path = str(pathlib.Path(os.path.dirname(__file__), CONFIG_PATH))
    with open(path, "r") as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


def draw_panel(config, img):
    power_graph_img = create_power_graph(
        config["INFLUXDB"], config["POWER"], config["FONT"]
    )
    sensor_graph_img = create_sensor_graph(
        config["INFLUXDB"], config["SENSOR"], config["FONT"]
    )

    weather_panel_img = create_weather_panel(config["WEATHER"], config["FONT"])

    img.paste(
        power_graph_img, (0, config["WEATHER"]["HEIGHT"] - config["POWER"]["OVERLAP"])
    )

    img.alpha_composite(weather_panel_img, (0, 0))
    img.paste(
        sensor_graph_img,
        (
            0,
            config["WEATHER"]["HEIGHT"]
            + config["POWER"]["HEIGHT"]
            - config["POWER"]["OVERLAP"]
            - config["SENSOR"]["OVERLAP"],
        ),
    )


######################################################################
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
        "\n".join(textwrap.wrap(traceback.format_exc(), 45)),
        [20, 200],
        get_font(config["FONT"], "EN_MEDIUM", 40),
        "left" "#333",
    )
    print(traceback.format_exc(), file=sys.stderr)

img.save(sys.stdout.buffer, "PNG")

exit(0)
