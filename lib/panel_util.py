#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import textwrap
import time
import traceback

import notify_slack
import PIL.Image
import PIL.ImageDraw
from pil_util import draw_text, get_font


def notify_error(config, message):
    logging.error(message)

    if "SLACK" not in config:
        return

    notify_slack.error(
        config["SLACK"]["BOT_TOKEN"],
        config["SLACK"]["ERROR"]["CHANNEL"]["NAME"],
        config["SLACK"]["FROM"],
        message,
        config["SLACK"]["ERROR"]["INTERVAL_MIN"],
    )


def error_image(panel_config, font_config, message):
    img = PIL.Image.new(
        "RGBA",
        (panel_config["PANEL"]["WIDTH"], panel_config["PANEL"]["HEIGHT"]),
        (255, 255, 255, 100),
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
        "\n".join(textwrap.wrap(message, 90)),
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

    error_message = None
    for i in range(5):
        try:
            return (
                func(panel_config, font_config, slack_config, is_side_by_side, opt_config),
                time.perf_counter() - start,
            )
        except:
            error_message = traceback.format_exc()
            logging.error(error_message)
            pass
        logging.warning("retry")
        time.sleep(5)

    return (
        error_image(panel_config, font_config, error_message),
        time.perf_counter() - start,
        error_message,
    )
