#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
時刻の画像を生成します．

Usage:
  time_panel.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

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
    time_text = (
        datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), "JST"))
        + datetime.timedelta(minutes=1)
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
        panel_config["PANEL"]["WIDTH"] - 20,
        panel_config["PANEL"]["HEIGHT"] - 20,
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


if __name__ == "__main__":
    from docopt import docopt

    import logger
    from config import load_config
    from pil_util import convert_to_gray

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])
    out_file = args["-o"]

    img = create_time_panel(config)[0]

    logging.info("Save {out_file}.".format(out_file=out_file))
    convert_to_gray(img).save(out_file, "PNG")

    print("Finish.")
