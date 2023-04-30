#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from urllib import request
from urllib.parse import urlparse
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageEnhance
import datetime
import locale
import math
import numpy as np
import os
import datetime
import pathlib
import logging

from pil_util import get_font, text_size, draw_text


def get_face_map(font_config):
    return {
        "time": {
            "value": get_font(font_config, "EN_BOLD", 130),
        },
    }


def draw_time(img, pos_x, pos_y, face):
    alpha = 255
    radius = 30
    padding = 4

    time_text = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9), "JST")
    ).strftime("%H:%M")

    text_width, text_height = text_size(face["value"], time_text)

    pos_y -= text_height

    draw = PIL.ImageDraw.Draw(img)
    draw.rounded_rectangle(
        (
            pos_x - padding - text_width,
            pos_y - padding,
            pos_x + padding,
            pos_y + padding + text_height,
        ),
        fill=(255, 255, 255, alpha),
        radius=radius,
    )

    draw_text(img, time_text, (pos_x, pos_y), face["value"], "right")


def draw_panel_time(img, config):
    panel_config = config["TIME"]
    font_config = config["FONT"]

    face_map = get_face_map(font_config)

    draw_time(
        img,
        config["PANEL"]["DEVICE"]["WIDTH"] - panel_config["PANEL"]["MARGIN_X"],
        config["PANEL"]["DEVICE"]["HEIGHT"] - panel_config["PANEL"]["MARGIN_Y"],
        face_map["time"],
    )


def create_time_panel(config):
    logging.info("draw time panel")

    img = PIL.Image.new(
        "RGBA",
        (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        (255, 255, 255, 0),
    )

    draw_panel_time(img, config)

    return img
