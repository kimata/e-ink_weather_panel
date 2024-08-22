#!/usr/bin/env python3
"""
天気予報画像を生成します．

Usage:
  weather_panel.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

import datetime
import locale
import logging
import math
import pathlib
import urllib
import urllib.parse

import cv2
import my_lib.panel_util
import my_lib.pil_util
import my_lib.weather
import numpy as np
import PIL.Image
import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont
from my_lib.weather import get_weather_yahoo

# NOTE: 天気アイコンの周りにアイコンサイズの何倍の空きを確保するか
ICON_MARGIN = 0.48

# NOTE: 現在の時間に対応する時間帯に描画する円の大きさ比率
HOUR_CIRCLE_RATIO = 1.6

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
            "month": my_lib.pil_util.get_font(font_config, "en_cond_bold", 60),
            "day": my_lib.pil_util.get_font(font_config, "en_bold", 160),
            "wday": my_lib.pil_util.get_font(font_config, "jp_bold", 80),
            "time": my_lib.pil_util.get_font(font_config, "en_cond_bold", 40),
        },
        "sunset": {
            "value": my_lib.pil_util.get_font(font_config, "en_cond", 70),
        },
        "hour": {
            "value": my_lib.pil_util.get_font(font_config, "en_medium", 60),
        },
        "temp": {
            "value": my_lib.pil_util.get_font(font_config, "en_bold", 120),
            "zero": my_lib.pil_util.get_font(font_config, "en_bold", 80),
            "unit": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
        },
        "temp_sens": {
            "value": my_lib.pil_util.get_font(font_config, "en_bold", 120),
            "unit": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
        },
        "precip": {
            "value": my_lib.pil_util.get_font(font_config, "en_bold", 120),
            "zero": my_lib.pil_util.get_font(font_config, "en_bold", 80),
            "unit": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
        },
        "wind": {
            "value": my_lib.pil_util.get_font(font_config, "en_bold", 120),
            "unit": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
            "dir": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
        },
        "weather": {
            "value": my_lib.pil_util.get_font(font_config, "jp_regular", 30),
        },
    }


def get_image(weather_info):
    tone = 32
    gamma = 0.24

    file_bytes = np.asarray(
        bytearray(urllib.request.urlopen(weather_info["icon_url"]).read()),  # noqa: S310
        dtype=np.uint8,
    )
    img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)

    # NOTE: 透過部分を白で塗りつぶす
    img[img[..., -1] == 0] = [255, 255, 255, 0]
    img = img[:, :, :3]

    dump_path = str(
        pathlib.Path(__file__).parent
        / "img"
        / (
            weather_info["text"]
            + "_"
            + pathlib.Path(urllib.parse.urlparse(weather_info["icon_url"]).path).name
        )
    )

    PIL.Image.fromarray(img).save(dump_path)

    h, w = img.shape[:2]

    # NOTE: 一旦4倍の解像度に増やす
    sr = cv2.dnn_superres.DnnSuperResImpl_create()

    model_path = str(pathlib.Path(__file__).parent / "data" / "ESPCN_x4.pb")

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


# NOTE: 体感温度の計算 (Gregorczuk, 1972)
def calc_misnar_formula(temp, humi, wind):
    a = 1.76 + 1.4 * (wind**0.75)
    return 37 - (37 - temp) / (0.68 - 0.0014 * humi + 1 / a) - 0.29 * temp * (1 - humi / 100)


def draw_weather(img, weather, overlay, pos_x, pos_y, icon_margin, face_map):  # noqa: PLR0913
    icon = get_image(weather)

    canvas = overlay.copy()
    canvas.paste(icon, (int(pos_x), int(pos_y)))
    img.alpha_composite(canvas, (0, 0))

    next_pos_y = pos_y
    next_pos_y += icon.size[1] * 1.08
    next_pos_y = my_lib.pil_util.draw_text(
        img,
        weather["text"],
        [pos_x + icon.size[0] / 2.0, next_pos_y],
        face_map["weather"]["value"],
        "center",
    )[1]

    return [pos_x + icon.size[0] * (1 + icon_margin), next_pos_y]


def draw_text_info(  # noqa: PLR0913
    img,
    value,
    unit,
    is_first,
    pos_x,
    pos_y,
    icon,
    face,
    color="#000",
    underline=False,
    margin_top_ratio=0.3,
):
    pos_y += my_lib.pil_util.text_size(img, face["value"], "0")[1] * margin_top_ratio

    if is_first:
        my_lib.pil_util.alpha_paste(
            img,
            icon,
            (
                int(pos_x - icon.size[0] / 2 - my_lib.pil_util.text_size(img, face["value"], "0")[0] * 0.4),
                int(pos_y + (my_lib.pil_util.text_size(img, face["value"], "0")[1] - icon.size[1]) / 2.0),
            ),
        )

    value_pos_x = pos_x + my_lib.pil_util.text_size(img, face["value"], "10")[0]
    unit_pos_y = (
        pos_y
        + my_lib.pil_util.text_size(img, face["value"], "0")[1]
        - my_lib.pil_util.text_size(img, face["unit"], "℃")[1]
    )
    unit_pos_x = value_pos_x + 5

    if (value > 0.01) and (value < 1) and ("zero" in face):
        tenth_text = str(int(value * 10))
        # NOTE: 小数点第一位
        my_lib.pil_util.draw_text(
            img,
            tenth_text,
            [value_pos_x, pos_y],
            face["value"],
            "right",
            color,
        )
        int_pos_x = value_pos_x - my_lib.pil_util.text_size(img, face["value"], tenth_text)[0]
        int_pos_y = pos_y + (
            my_lib.pil_util.text_size(img, face["value"], tenth_text)[1]
            - my_lib.pil_util.text_size(img, face["zero"], "0.")[1]
        )
        my_lib.pil_util.draw_text(
            img,
            "0.",
            [int_pos_x, int_pos_y],
            face["zero"],
            "right",
            color,
        )
        value_start_x = int_pos_x - my_lib.pil_util.text_size(img, face["zero"], "0.")[0]
    else:
        if value < 0.01:
            value_text = "0"
        elif value < 1:
            value_text = f"{value:.1f}"
        else:
            value_text = f"{value:.0f}"

        my_lib.pil_util.draw_text(
            img,
            value_text,
            [value_pos_x, pos_y],
            face["value"],
            "right",
            color,
        )
        value_start_x = value_pos_x - my_lib.pil_util.text_size(img, face["value"], value_text)[0]

    next_pos_y = pos_y + my_lib.pil_util.text_size(img, face["value"], "0")[1]

    if underline:
        draw = PIL.ImageDraw.Draw(img)
        draw.rectangle(
            (
                value_start_x,
                next_pos_y + 4,
                value_pos_x,
                next_pos_y + 11,
            ),
            fill=(30, 30, 30),
        )

    my_lib.pil_util.draw_text(
        img,
        unit,
        [unit_pos_x, unit_pos_y],
        face["unit"],
        color,
    )

    return next_pos_y


def draw_temp(img, temp, is_first, pos_x, pos_y, icon, face):  # noqa: PLR0913
    return draw_text_info(
        img,
        int(temp),
        "℃",
        is_first,
        pos_x,
        pos_y,
        icon,
        face,
        underline=temp > 30 or temp < 0,
        margin_top_ratio=0.1,
    )


def draw_precip(img, precip, is_first, pos_x, pos_y, precip_icon, face):  # noqa: PLR0913
    if precip <= 0.01:
        color = "#eee"
        underline = False
    elif precip <= 1:
        color = "#ddd"
        underline = False
    elif precip <= 2:
        color = "#bbb"
        underline = False
    elif precip < 10:
        color = "#666"
        underline = False
    elif precip < 20:
        color = "#333"
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
        face,
        color=color,
        underline=underline,
    )


def draw_wind(img, wind, is_first, pos_x, pos_y, icon, face):  # noqa: PLR0913
    pos_y += my_lib.pil_util.text_size(img, face["value"], "0")[1] * 0.2  # NOTE: 上にマージンを設ける

    if wind["speed"] == 0:
        color = "#eee"
        brightness = 8
    elif wind["speed"] == 1:
        color = "#ddd"
        brightness = 7.5
    elif wind["speed"] == 2:
        color = "#bbb"
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
        arrow_icon = PIL.ImageEnhance.Brightness(icon["arrow"]).enhance(brightness)
        arrow_icon = arrow_icon.rotate(
            ROTATION_MAP[wind["dir"]],
            resample=PIL.Image.BICUBIC,
        )

        my_lib.pil_util.alpha_paste(
            img,
            arrow_icon,
            (
                int(pos_x + my_lib.pil_util.text_size(img, face["value"], "10")[0] - arrow_icon.size[0]),
                int(pos_y + (icon_orig_height - icon["arrow"].size[1]) / 2.0),
            ),
        )

    pos_y += icon_orig_height + 5

    next_pos_y = draw_text_info(
        img,
        wind["speed"],
        "m/s",
        is_first,
        pos_x,
        pos_y,
        icon["wind"],
        face,
        color,
        margin_top_ratio=0,
    )

    next_pos_y += (
        my_lib.pil_util.text_size(
            img,
            face["dir"],
            "南",
        )[1]
        * 0.2
    )

    return my_lib.pil_util.draw_text(
        img,
        wind["dir"],
        [
            pos_x + my_lib.pil_util.text_size(img, face["value"], "10")[0],
            next_pos_y,
        ],
        face["dir"],
        "right",
        color=color,
    )[1]


def draw_hour(img, hour, is_today, pos_x, pos_y, face_map):  # noqa: PLR0913
    face = face_map["hour"]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))
    cur_hour = now.hour

    if is_today and (
        (abs((now - now.replace(hour=hour)).total_seconds()) < (60 * (60 + 30)))
        or (cur_hour < 6 and hour == 6)
        or (cur_hour >= 21 and hour == 21)
    ):
        draw = PIL.ImageDraw.Draw(img)
        circle_height = my_lib.pil_util.text_size(img, face["value"], str(21))[1]

        draw.ellipse(
            (
                pos_x - circle_height * HOUR_CIRCLE_RATIO / 2.0,
                pos_y - circle_height * HOUR_CIRCLE_RATIO / 2.0 + circle_height / 2,
                pos_x + circle_height * HOUR_CIRCLE_RATIO / 2.0,
                pos_y + circle_height * HOUR_CIRCLE_RATIO / 2.0 + circle_height / 2,
            ),
            fill=(128, 128, 128),
        )
        my_lib.pil_util.draw_text(
            img,
            str(hour),
            [pos_x, pos_y],
            face["value"],
            "center",
            "#FFF",
        )
    else:
        my_lib.pil_util.draw_text(
            img,
            str(hour),
            [pos_x, pos_y],
            face["value"],
            "center",
        )

    return pos_y + my_lib.pil_util.text_size(img, face["value"], "0")[1]


def draw_weather_info(  # noqa: PLR0913
    img,
    info,
    wbgt_info,
    is_wbgt_exist,
    is_today,
    is_first,
    pos_x,
    pos_y,
    overlay,
    icon,
    face_map,
):
    next_pos_y = pos_y + my_lib.pil_util.text_size(img, face_map["hour"]["value"], "0")[1] * HOUR_CIRCLE_RATIO
    next_pos_x, next_pos_y = draw_weather(
        img, info["weather"], overlay, pos_x, next_pos_y, ICON_MARGIN, face_map
    )
    draw_hour(
        img,
        info["hour"],
        is_today,
        pos_x + (next_pos_x - pos_x) / ((1 + ICON_MARGIN) * 2.0),
        pos_y,
        face_map,
    )
    next_pos_y += 30
    next_pos_y = draw_temp(
        img,
        info["temp"],
        is_first,
        pos_x,
        next_pos_y,
        icon["thermo"],
        face_map["temp"],
    )
    next_pos_y += 20
    next_pos_y = draw_precip(
        img,
        info["precip"],
        is_first,
        pos_x,
        next_pos_y,
        icon["precip"],
        face_map["precip"],
    )
    next_pos_y += 10
    next_pos_y = draw_wind(
        img,
        info["wind"],
        is_first,
        pos_x,
        next_pos_y,
        icon,
        face_map["wind"],
    )
    next_pos_y += 30
    if is_wbgt_exist:
        next_pos_y = draw_temp(
            img,
            wbgt_info,
            is_first,
            pos_x,
            next_pos_y,
            icon["sun"],
            face_map["temp_sens"],
        )
    else:
        temp_sens = calc_misnar_formula(info["temp"], info["humi"], info["wind"]["speed"])
        next_pos_y = draw_temp(
            img,
            int(temp_sens),
            is_first,
            pos_x,
            next_pos_y,
            icon["clothes"],
            face_map["temp_sens"],
        )

    return pos_x + (next_pos_x - pos_x) * 1.0


def draw_day_weather(img, info, wbgt_info, is_today, pos_x, pos_y, overlay, icon, face_map):  # noqa: PLR0913
    next_pos_x = pos_x
    for hour_index in range(2, 8):
        next_pos_x = draw_weather_info(
            img,
            info[hour_index],
            wbgt_info[hour_index] if wbgt_info is not None else None,
            wbgt_info is not None,
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

    next_pos_x = pos_x + my_lib.pil_util.text_size(img, face["day"], "31")[0]
    text_pos_x = (pos_x + next_pos_x) / 2.0

    locale.setlocale(locale.LC_TIME, "en_US.UTF-8")
    next_pos_y = my_lib.pil_util.draw_text(
        img,
        date.strftime("%B"),
        [text_pos_x, pos_y],
        face["month"],
        "center",
        "#666",
    )[1]
    next_pos_y = my_lib.pil_util.draw_text(
        img,
        str(date.day),
        [text_pos_x, next_pos_y + 14],
        face["day"],
        "center",
        "#666",
    )[1]
    locale.setlocale(locale.LC_TIME, "ja_JP.UTF-8")
    next_pos_y = my_lib.pil_util.draw_text(
        img,
        date.strftime("(%a)"),
        [
            text_pos_x,
            next_pos_y + my_lib.pil_util.text_size(img, face["wday"], "(土)")[1] * 0.2,
        ],
        face["wday"],
        "center",
        "#666",
    )[1]

    return (next_pos_x, next_pos_y, text_pos_x)


def draw_sunset(img, pos_x, pos_y, sunset_info, icon, face_map):  # noqa: PLR0913
    OFFSET = 10
    face = face_map["sunset"]

    icon_width, icon_height = icon["sunset"].size
    text_width, text_height = my_lib.pil_util.text_size(img, face["value"], sunset_info)

    icon_pos = (
        int(pos_x - text_width / 2 - icon_width + OFFSET),
        int(pos_y + text_height / 2 - icon_height / 2),
    )

    my_lib.pil_util.alpha_paste(img, icon["sunset"], icon_pos)

    return my_lib.pil_util.draw_text(
        img,
        sunset_info,
        [pos_x + OFFSET, pos_y],
        face["value"],
        "center",
        "#000",
    )[1]


def draw_clothing(img, pos_x, pos_y, clothing_info, icon):
    icon_index = math.ceil(clothing_info / 20)
    if icon_index == 0:
        icon_index += 1

    icon_height_max = 0
    for i in range(1, 6):
        icon_height_max = max(icon[f"clothing-full-{i}"].size[1], icon_height_max)

    full_icon = icon[f"clothing-full-{icon_index}"]
    half_icon = icon[f"clothing-half-{icon_index}"]
    icon_width, icon_height = full_icon.size

    shadow_icon = PIL.ImageEnhance.Brightness(full_icon).enhance(1.9)

    for i in range(5):
        if clothing_info >= 20 * (i + 1):
            draw_icon = full_icon
        elif clothing_info >= (20 * i + 10):
            draw_icon = half_icon
        else:
            draw_icon = shadow_icon

        # NOTE: サイズ違いの場合，やや上寄りにする
        icon_pos = (
            int(pos_x - icon_width / 2),
            int(pos_y + (icon_height_max - draw_icon.size[1]) / 3),
        )

        my_lib.pil_util.alpha_paste(img, draw_icon, icon_pos)

        pos_y += icon_height_max * 1.05


def draw_panel_weather_day(  # noqa: PLR0913
    img,
    pos_x,
    pos_y,
    weather_day_info,
    clothing_info,
    sunset_info,
    wbgt_info,
    is_today,
    overlay,
    icon,
    face_map,
):
    date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))
    if not is_today:
        date += datetime.timedelta(days=1)

    next_pos_x, next_pos_y, text_pos_x = draw_date(img, pos_x, pos_y, date, face_map)
    next_pos_y = draw_sunset(img, text_pos_x, next_pos_y + 20, sunset_info, icon, face_map)
    draw_clothing(img, text_pos_x, next_pos_y + 20, clothing_info, icon)
    draw_day_weather(
        img,
        weather_day_info,
        wbgt_info,
        is_today,
        next_pos_x + 50,
        pos_y + 5,
        overlay,
        icon,
        face_map,
    )


def draw_panel_weather(  # noqa: PLR0913
    img,
    panel_config,
    font_config,
    weather_info,
    clothing_info,
    sunset_info,
    wbgt_info,
    is_side_by_side,
):
    icon = {}
    for name in [
        "sunset",
        "thermo",
        "clothes",
        "precip",
        "wind",
        "arrow",
        "sun",
        "clothing-full-1",
        "clothing-full-2",
        "clothing-full-3",
        "clothing-full-4",
        "clothing-full-5",
        "clothing-half-1",
        "clothing-half-2",
        "clothing-half-3",
        "clothing-half-4",
        "clothing-half-5",
    ]:
        icon[name] = my_lib.pil_util.load_image(panel_config["icon"][name])

    face_map = get_face_map(font_config)

    pos_x = 10
    pos_y = 20

    draw_panel_weather_day(
        img,
        pos_x,
        pos_y,
        weather_info["today"],
        clothing_info["today"],
        sunset_info["today"],
        wbgt_info["daily"]["today"],
        True,
        img.copy(),
        icon,
        face_map,
    )
    if is_side_by_side:
        pos_x += panel_config["panel"]["width"] / 2.0
    else:
        pos_y += panel_config["panel"]["height"] / 2.0

    draw_panel_weather_day(
        img,
        pos_x,
        pos_y,
        weather_info["tomorrow"],
        clothing_info["tomorrow"],
        sunset_info["tomorrow"],
        wbgt_info["daily"]["tomorrow"],
        False,
        img.copy(),
        icon,
        face_map,
    )


def create_weather_panel_impl(panel_config, font_config, slack_config, is_side_by_side, trial, opt_config):  # noqa: ARG001, PLR0913
    weather_info = get_weather_yahoo(panel_config["data"]["yahoo"])
    clothing_info = my_lib.weather.get_clothing_yahoo(panel_config["data"]["yahoo"])
    sunset_info = my_lib.weather.get_sunset_nao(opt_config["sunset"])
    wbgt_info = my_lib.weather.get_wbgt(opt_config["wbgt"])

    img = PIL.Image.new(
        "RGBA",
        (panel_config["panel"]["width"], panel_config["panel"]["height"]),
        (255, 255, 255, 0),
    )

    draw_panel_weather(
        img,
        panel_config,
        font_config,
        weather_info,
        clothing_info,
        sunset_info,
        wbgt_info,
        is_side_by_side,
    )

    return img


def create(config, is_side_by_side=True):
    logging.info("draw weather panel")

    return my_lib.panel_util.draw_panel_patiently(
        create_weather_panel_impl,
        config["weather"],
        config["font"],
        None,
        is_side_by_side,
        {"sunset": config["sunset"], "wbgt": config["wbgt"]},
    )


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    out_file = args["-o"]

    img = create_weather_panel_impl(
        config["weather"],
        config["font"],
        None,
        True,
        1,
        {"sunset": config["sunset"], "wbgt": config["wbgt"]},
    )

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
