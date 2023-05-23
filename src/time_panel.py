#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageEnhance
import time
import datetime
import logging

from pil_util import get_font, text_size, draw_text


def get_face_map(font_config):
    return {
        "time": {
            "value": get_font(font_config, "EN_BOLD", 130),
        },
    }


def draw_time(img, pos_x, pos_y, face):
    time_text = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9), "JST")
    ).strftime("%H:%M")

    pos_y -= text_size(face["value"], time_text)[1]

    draw_text(
        img,
        time_text,
        (pos_x, pos_y),
        face["value"],
        "right",
        "#333333",
        stroke_width=20,
        stroke_fill=(255, 255, 255, 200),
    )


def draw_panel_time(img, config):
    panel_config = config["TIME"]
    font_config = config["FONT"]

    face_map = get_face_map(font_config)

    # 右下に描画する
    draw_time(
        img,
        panel_config["PANEL"]["WIDTH"],
        panel_config["PANEL"]["HEIGHT"],
        face_map["time"],
    )


def create_time_panel(config):
    logging.info("draw time panel")
    start = time.perf_counter()

    img = PIL.Image.new(
        "RGBA",
        (config["TIME"]["PANEL"]["WIDTH"], config["TIME"]["PANEL"]["HEIGHT"]),
        (255, 255, 255, 0),
    )

    draw_panel_time(img, config)

    return (img, time.perf_counter() - start)
