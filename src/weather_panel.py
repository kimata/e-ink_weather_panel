#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from cv2 import dnn_superres
from urllib import request
from urllib.parse import urlparse
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import PIL.ImageEnhance
import cv2
import datetime
import locale
import math
import numpy as np
import os
import pathlib
import logging

from pil_util import get_font, text_size, draw_text
from weather_data import get_weather_yahoo

# NOTE: 天気アイコンの周りにアイコンサイズの何倍の空きを確保するか
ICON_MARGIN = 0.24

# NOTE: 現在の時間に対応する時間帯に描画する円の大きさ比率
HOUR_CIRCLE_RATIO = 1.5


ROTATION_MAP = {
    "静穏": None,
    "東": 90,
    "西": 270,
    "南": 0,
    "北": 180,
    "北東": 135,
    "北西": 225,
    "南東": 45,
    "南西": 315,
    "北北東": 158,
    "北北西": 203,
    "南南東": 23,
    "南南西": 337,
    "東北東": 113,
    "東南東": 67,
    "西北西": 247,
    "西南西": 293,
}


def get_face_map(font_config):
    return {
        "date": {
            "month": get_font(font_config, "EN_COND_BOLD", 60),
            "day": get_font(font_config, "EN_BOLD", 160),
            "wday": get_font(font_config, "JP_BOLD", 100),
            "time": get_font(font_config, "EN_COND_BOLD", 40),
        },
        "hour": {
            "value": get_font(font_config, "EN_MEDIUM", 60),
        },
        "temp": {
            "value": get_font(font_config, "EN_BOLD", 120),
            "unit": get_font(font_config, "JP_REGULAR", 30),
        },
        "precip": {
            "value": get_font(font_config, "EN_BOLD", 120),
            "unit": get_font(font_config, "JP_REGULAR", 30),
        },
        "wind": {
            "value": get_font(font_config, "EN_BOLD", 120),
            "unit": get_font(font_config, "JP_REGULAR", 30),
            "dir": get_font(font_config, "JP_REGULAR", 42),
        },
        "weather": {
            "value": get_font(font_config, "JP_REGULAR", 30),
        },
    }


def get_image(weather_info):
    tone = 32
    gamma = 0.24

    file_bytes = np.asarray(
        bytearray(request.urlopen(weather_info["icon_url"]).read()), dtype=np.uint8
    )
    img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

    # NOTE: 透過部分を白で塗りつぶす
    img[img[..., -1] == 0] = [255, 255, 255, 0]
    img = img[:, :, :3]

    dump_path = str(
        pathlib.Path(
            os.path.dirname(__file__),
            "img",
            weather_info["text"]
            + "_"
            + os.path.basename(urlparse(weather_info["icon_url"]).path),
        )
    )

    PIL.Image.fromarray(img).save(dump_path)

    h, w = img.shape[:2]

    # NOTE: 一旦4倍の解像度に増やす
    sr = dnn_superres.DnnSuperResImpl_create()

    model_path = str(pathlib.Path(os.path.dirname(__file__), "data", "ESPCN_x4.pb"))

    sr.readModel(model_path)
    sr.setModel("espcn", 4)
    img = sr.upsample(img)

    # NOTE: 階調を削減
    tone_table = np.zeros((256, 1), dtype=np.uint8)
    for i in range(256):
        tone_table[i][0] = min(math.ceil(i / tone) * tone, 255)
    img = cv2.LUT(img, tone_table)

    # NOTE: ガンマ補正
    gamma_table = np.zeros((256, 1), dtype=np.uint8)
    for i in range(256):
        gamma_table[i][0] = 255 * (float(i) / 255) ** (1.0 / gamma)
    img = cv2.LUT(img, gamma_table)

    # NOTE: 最終的に欲しい解像度にする
    img = cv2.resize(img, (int(w * 1.9), int(h * 1.9)), interpolation=cv2.INTER_CUBIC)

    # NOTE: 白色を透明にする
    img = cv2.cvtColor(img, cv2.COLOR_RGB2RGBA)
    img[:, :, 3] = np.where(np.all(img == 255, axis=-1), 0, 255)

    return PIL.Image.fromarray(img).convert("LA")


def draw_weather(img, weather, overlay, pos_x, pos_y, icon_margin, face_map):
    icon = get_image(weather)

    pos_x += icon.size[0] * icon_margin / 2.0

    canvas = overlay.copy()
    canvas.paste(icon, (int(pos_x), int(pos_y)))
    img.alpha_composite(canvas, (0, 0))

    next_pos_y = pos_y
    next_pos_y += icon.size[1] * 1.1
    next_pos_y = draw_text(
        img,
        weather["text"],
        [pos_x + icon.size[0] / 2.0, next_pos_y],
        face_map["weather"]["value"],
        "center",
    )[1]

    return [pos_x + icon.size[0] * (1 + icon_margin), next_pos_y]


def draw_text_info(
    img, value, unit, is_first, pos_x, pos_y, icon, face, color="#000", underline=False
):
    pos_y += text_size(face["value"], "-10")[1] * 0.4  # NOTE: 上にマージンを設ける

    if is_first:
        img.paste(
            icon,
            (
                int(pos_x - icon.size[0] - text_size(face["value"], "0")[0] * 0.1),
                int(pos_y + (text_size(face["value"], "-10")[1] - icon.size[1]) / 2.0),
            ),
        )

    value_pos_x = pos_x + text_size(face["value"], "-10")[0]
    unit_pos_y = (
        pos_y + text_size(face["value"], "0")[1] - text_size(face["unit"], "℃")[1]
    )
    unit_pos_x = value_pos_x + 5

    draw_text(
        img, str(value), [value_pos_x, pos_y], face["value"], "right", color=color
    )

    next_pos_y = pos_y + text_size(face["value"], "0")[1]

    if underline:
        draw = PIL.ImageDraw.Draw(img)
        draw.rectangle(
            (
                value_pos_x - text_size(face["value"], str(value))[0],
                next_pos_y + 8,
                value_pos_x,
                next_pos_y + 15,
            ),
            fill=(90, 90, 90),
        )

    draw_text(img, unit, [unit_pos_x, unit_pos_y], face["unit"], color=color)[0]

    return next_pos_y


def draw_temp(img, temp, is_first, pos_x, pos_y, thermo_icon, face_map):
    if temp >= 30 or temp < 5:
        underline = True
    else:
        underline = False

    return draw_text_info(
        img,
        temp,
        "℃",
        is_first,
        pos_x,
        pos_y,
        thermo_icon,
        face_map["temp"],
        underline=underline,
    )


def draw_precip(img, precip, is_first, pos_x, pos_y, precip_icon, face_map):
    if precip == 0:
        color = "#eee"
        underline = False
    elif precip < 3:
        color = "#ddd"
        underline = False
    elif precip < 10:
        color = "#666"
        underline = False
    else:
        color = "#000"
        underline = True

    return draw_text_info(
        img,
        precip,
        "mm",
        is_first,
        pos_x,
        pos_y,
        precip_icon,
        face_map["precip"],
        color=color,
        underline=underline,
    )


def draw_wind(img, wind, is_first, pos_x, pos_y, width, overlay, icon, face_map):
    face = face_map["wind"]
    pos_y += text_size(face["value"], "-10")[1] * 0.2  # NOTE: 上にマージンを設ける

    if wind["speed"] == 0:
        color = "#eee"
        brightness = 8
    elif wind["speed"] == 1:
        color = "#ddd"
        brightness = 7.5
    elif wind["speed"] == 2:
        color = "#ccc"
        brightness = 6.5
    elif wind["speed"] == 3:
        color = "#999"
        brightness = 5.5
    elif wind["speed"] == 4:
        color = "#666"
        brightness = 3
    else:
        color = "#000"
        brightness = 1

    icon_orig_height = icon["arrow"].size[1]
    if ROTATION_MAP[wind["dir"]] is not None:
        arrow_icon = icon["arrow"].rotate(
            ROTATION_MAP[wind["dir"]],
            resample=PIL.Image.BICUBIC,
        )
        arrow_icon = PIL.ImageEnhance.Brightness(arrow_icon).enhance(brightness)

        canvas = overlay.copy()
        canvas.paste(
            arrow_icon,
            (
                int(pos_x + width * 1.4 / 2.0 - arrow_icon.size[0] / 2.0),
                int(pos_y + (icon_orig_height - icon["arrow"].size[1]) / 2.0),
            ),
        )
        img.alpha_composite(canvas, (0, 0))

    pos_y += icon_orig_height

    value_pos_x = pos_x + text_size(face["value"], "-10")[0]
    unit_pos_y = (
        pos_y + text_size(face["value"], "0")[1] - text_size(face["unit"], "m/s")[1]
    )
    unit_pos_x = value_pos_x + 5

    if is_first:
        img.paste(
            icon["wind"],
            (
                int(pos_x - text_size(face["value"], "0")[0] * 1.5),
                int(
                    pos_y
                    + (text_size(face["value"], "-10")[1] - icon["wind"].size[1]) / 2.0
                ),
            ),
        )

    next_pos_y = draw_text(
        img,
        str(wind["speed"]),
        [value_pos_x, pos_y],
        face["value"],
        "right",
        color=color,
    )[1]
    draw_text(img, "m/s", [unit_pos_x, unit_pos_y], face["unit"], color=color)[0]

    next_pos_y += text_size(
        face["dir"],
        "南",
        need_padding_change=False,
    )[1]
    next_pos_y = draw_text(
        img,
        wind["dir"],
        [value_pos_x, next_pos_y],
        face["dir"],
        "right",
        color=color,
        need_padding_change=False,
    )[1]

    return next_pos_y + text_size(face["value"], "南")[1]


def draw_hour(img, hour, is_today, pos_x, pos_y, face_map):
    face = face_map["hour"]

    cur_hour = datetime.datetime.now().hour
    if is_today and (
        (hour <= cur_hour and cur_hour < hour + 3)
        or (cur_hour < 6 and hour == 6)
        or (21 <= cur_hour and hour == 21)
    ):
        draw = PIL.ImageDraw.Draw(img)
        circle_height = text_size(face["value"], str(21))[1]

        draw.ellipse(
            (
                pos_x - circle_height * HOUR_CIRCLE_RATIO / 2.0,
                pos_y - circle_height * (HOUR_CIRCLE_RATIO - 1 - 0.2) / 2.0,
                pos_x + circle_height * HOUR_CIRCLE_RATIO / 2.0,
                pos_y + circle_height * (1 + HOUR_CIRCLE_RATIO + 0.2) / 2.0,
            ),
            fill=(128, 128, 128),
        )
        draw_text(img, str(hour), [pos_x, pos_y], face["value"], "center", "#FFF")
    else:
        draw_text(img, str(hour), [pos_x, pos_y], face["value"], "center")

    return pos_y + text_size(face["value"], "0")[1]


def draw_weather_info(
    img, info, is_today, is_first, pos_x, pos_y, overlay, icon, face_map
):
    next_pos_y = (
        pos_y + text_size(face_map["hour"]["value"], "0")[1] * HOUR_CIRCLE_RATIO
    )
    next_pos_x, next_pos_y = draw_weather(
        img, info["weather"], overlay, pos_x, next_pos_y, ICON_MARGIN, face_map
    )
    draw_hour(img, info["hour"], is_today, (pos_x + next_pos_x) / 2.0, pos_y, face_map)
    next_pos_y = draw_temp(
        img, info["temp"], is_first, pos_x, next_pos_y, icon["thermo"], face_map
    )
    next_pos_y = draw_precip(
        img, info["precip"], is_first, pos_x, next_pos_y, icon["precip"], face_map
    )
    next_pos_y = draw_wind(
        img,
        info["wind"],
        is_first,
        pos_x,
        next_pos_y,
        next_pos_x - pos_x,
        overlay,
        icon,
        face_map,
    )

    return pos_x + (next_pos_x - pos_x) * 1.0


def draw_day_weather(img, info, is_today, pos_x, pos_y, overlay, icon, face_map):
    next_pos_x = pos_x
    for hour_index in range(2, 8):
        next_pos_x = draw_weather_info(
            img,
            info[hour_index],
            is_today,
            hour_index == 2,
            next_pos_x,
            pos_y,
            overlay,
            icon,
            face_map,
        )


def draw_date(img, pos_x, pos_y, date, face_map):
    face = face_map["date"]

    next_pos_x = pos_x + text_size(face["day"], "31")[0]
    text_pos_x = (pos_x + next_pos_x) / 2.0

    locale.setlocale(locale.LC_TIME, "en_US.UTF-8")
    next_pos_y = draw_text(
        img,
        date.strftime("%B"),
        [text_pos_x, pos_y],
        face["month"],
        "center",
        "#666",
        need_padding_change=False,
    )[1]
    next_pos_y = draw_text(
        img,
        str(date.day),
        [text_pos_x, next_pos_y],
        face["day"],
        "center",
        "#666",
    )[1]
    locale.setlocale(locale.LC_TIME, "ja_JP.UTF-8")
    draw_text(
        img,
        date.strftime("(%a)"),
        [text_pos_x, next_pos_y + text_size(face["day"], "31")[1] * 0.4],
        face["wday"],
        "center",
        "#666",
        need_padding_change=False,
    )[0]

    return next_pos_x


def draw_panel_weather_day(
    img, pos_x, pos_y, weather_day_info, is_today, overlay, icon, face_map
):
    next_pos_x = draw_date(
        img,
        pos_x,
        pos_y,
        datetime.datetime.now()
        if is_today
        else datetime.datetime.now() + datetime.timedelta(days=1),
        face_map,
    )
    draw_day_weather(
        img,
        weather_day_info,
        is_today,
        next_pos_x + 50,
        pos_y + 10,
        overlay,
        icon,
        face_map,
    )


def draw_panel_weather(img, config, weather_info):
    panel_config = config["WEATHER"]
    font_config = config["FONT"]

    icon = {}
    for name in ["thermo", "precip", "wind", "arrow"]:
        icon[name] = PIL.Image.open(
            str(
                pathlib.Path(
                    os.path.dirname(__file__), panel_config["ICON"][name.upper()]
                )
            )
        )

    face_map = get_face_map(font_config)

    pos_x = 10
    pos_y = 20
    draw_panel_weather_day(
        img,
        pos_x,
        pos_y,
        weather_info["today"],
        True,
        img.copy(),
        icon,
        face_map,
    )
    draw_panel_weather_day(
        img,
        pos_x + panel_config["PANEL"]["WIDTH"] / 2.0,
        pos_y,
        weather_info["tommorow"],
        False,
        img.copy(),
        icon,
        face_map,
    )


def create_weather_panel(config):
    logging.info("draw weather panel")

    weather_info = get_weather_yahoo(config["WEATHER"]["DATA"]["YAHOO"])
    img = PIL.Image.new(
        "RGBA",
        (config["WEATHER"]["PANEL"]["WIDTH"], config["WEATHER"]["PANEL"]["HEIGHT"]),
        (255, 255, 255, 0),
    )

    draw_panel_weather(img, config, weather_info)

    return img
