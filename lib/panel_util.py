#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import traceback
import logging
import PIL.Image
import PIL.ImageDraw
import textwrap

from pil_util import get_font, draw_text


def error_image(panel_config, font_config, error_text):
    img = PIL.Image.new(
        "RGBA",
        (panel_config["PANEL"]["WIDTH"], panel_config["PANEL"]["HEIGHT"]),
        (255, 255, 255, 255),
    )

    draw = PIL.ImageDraw.Draw(img)
    draw.rectangle(
        (0, 0, panel_config["PANEL"]["WIDTH"], panel_config["PANEL"]["HEIGHT"]),
        fill=(255, 255, 255, 255),
    )

    draw_text(
        img,
        "ERROR",
        (10, 10),
        get_font(font_config, "EN_BOLD", 100),
        "left",
        "#666",
    )

    draw_text(
        img,
        "\n".join(textwrap.wrap(error_text, 90)),
        (20, 150),
        get_font(font_config, "EN_MEDIUM", 30),
        "left" "#666",
    )

    return img


def draw_panel_patiently(
    func,
    panel_config,
    font_config,
    slack_config,
    is_side_by_side,
    opt_config=None,
):
    start = time.perf_counter()

    error_text = None
    for i in range(5):
        try:
            return (
                func(
                    panel_config, font_config, slack_config, is_side_by_side, opt_config
                ),
                time.perf_counter() - start,
            )
        except:
            error_text = traceback.format_exc()
            logging.error(error_text)
            pass
        logging.warning("retry")
        time.sleep(5)

    return (
        error_image(panel_config, font_config, error_text),
        time.perf_counter() - start,
    )
