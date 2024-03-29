#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
暑さ指数(WBGP)の画像を生成します．

Usage:
  wbgt_panel.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""


import logging

import PIL.Image
import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont
from panel_util import draw_panel_patiently
from pil_util import alpha_paste, draw_text, get_font, load_image
from weather_data import get_wbgt


def get_face_map(font_config):
    return {
        "wbgt": get_font(font_config, "EN_BOLD", 80),
        "wbgt_symbol": get_font(font_config, "JP_BOLD", 120),
        "wbgt_title": get_font(font_config, "JP_MEDIUM", 30),
    }


def draw_wbgt(img, wbgt, panel_config, icon_config, face_map):
    title = "暑さ指数:"
    wbgt_str = "{wbgt:.1f}".format(wbgt=wbgt)

    if wbgt >= 31:
        index = 4
    elif wbgt >= 28:
        index = 3
    elif wbgt >= 25:
        index = 2
    elif wbgt >= 21:
        index = 1
    else:
        index = 0

    icon = load_image(icon_config["FACE"][index])

    pos_x = panel_config["PANEL"]["WIDTH"] - 10
    pos_y = 10

    alpha_paste(
        img,
        icon,
        (int(pos_x - icon.size[0]), pos_y),
    )

    pos_y += icon.size[1] + 10

    next_pos_y = draw_text(
        img,
        title,
        (pos_x, pos_y),
        face_map["wbgt_title"],
        "right",
        "#333",
        stroke_width=10,
        stroke_fill=(255, 255, 255, 200),
    )[1]
    next_pos_y += 12
    draw_text(
        img,
        wbgt_str,
        (pos_x, next_pos_y),
        face_map["wbgt"],
        "right",
        "#333",
        stroke_width=10,
        stroke_fill=(255, 255, 255, 200),
    )

    return img


def create_wbgt_panel_impl(panel_config, font_config, slack_config, is_side_by_side, trial, opt_config=None):
    face_map = get_face_map(font_config)

    img = PIL.Image.new(
        "RGBA",
        (panel_config["PANEL"]["WIDTH"], panel_config["PANEL"]["HEIGHT"]),
        (255, 255, 255, 0),
    )

    wbgt = get_wbgt(panel_config)["current"]

    if wbgt is None:
        return img

    draw_wbgt(img, wbgt, panel_config, panel_config["ICON"], face_map)

    return img


def create(config, is_side_by_side=True):
    logging.info("draw WBGT panel")

    return draw_panel_patiently(
        create_wbgt_panel_impl, config["WBGT"], config["FONT"], None, is_side_by_side, error_image=False
    )


if __name__ == "__main__":
    import logger
    from config import load_config
    from docopt import docopt
    from pil_util import convert_to_gray

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])
    out_file = args["-o"]

    img = create(config)[0]

    logging.info("Save {out_file}.".format(out_file=out_file))
    convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
