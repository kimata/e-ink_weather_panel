#!/usr/bin/env python3
"""
雨雲レーダー画像を生成します．

Usage:
  rain_cloud_panel.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

import datetime
import logging
import pathlib
import time
import traceback

import my_lib.notify.slack
import my_lib.panel_util
import my_lib.pil_util
import PIL.Image
import PIL.ImageDraw
import pytz
from my_lib.sensor_data import fetch_data, get_last_event

DATA_PATH = pathlib.Path("data")
WINDOW_SIZE_CACHE = DATA_PATH / "window_size.cache"
CACHE_EXPIRE_HOUR = 1

CLOUD_IMAGE_XPATH = '//div[contains(@id, "jmatile_map_")]'


def get_face_map(font_config):
    return {
        "value": my_lib.pil_util.get_font(font_config, "en_bold", 80),
        "unit": my_lib.pil_util.get_font(font_config, "en_bold", 30),
        "start": my_lib.pil_util.get_font(font_config, "jp_medium", 40),
    }


def get_rainfall_status(panel_config, db_config):
    START = "-3m"

    data = fetch_data(
        db_config,
        panel_config["host"]["type"],
        panel_config["host"]["name"],
        "rain",
        start=START,
        window_min=None,
        last=True,
    )

    if not data["valid"]:
        return None

    amount = data["value"][0]

    # NOTE: 1分あたりの降水量なので，時間あたりに直す
    amount *= 60

    data = fetch_data(
        db_config,
        panel_config["host"]["type"],
        panel_config["host"]["name"],
        "raining",
        start=START,
        window_min=0,
        last=True,
    )

    raining_status = data["value"][0]

    if raining_status:
        raining_start = get_last_event(
            db_config, panel_config["host"]["type"], panel_config["host"]["name"], "raining"
        )
    else:
        raining_start = None

    return {
        "amount": amount,
        "raining": {
            "status": raining_status,
            "start": raining_start,
        },
    }


def gen_amount_text(amount):
    if amount >= 10:
        return str(int(amount))
    elif amount < 1:
        return f"{amount:.2f}"
    else:
        return f"{amount:.1f}"


def gen_start_text(start_time):
    delta = datetime.datetime.now(pytz.utc) - start_time.astimezone(pytz.utc)
    total_minutes = delta.total_seconds() // 60

    if total_minutes < 60:
        return f"({int(total_minutes)}分前)"
    elif total_minutes < 120:
        return f"(1時間{int(total_minutes - 60)}分前)"
    else:
        total_hours = total_minutes // 60
        return f"({int(total_hours)}時間前)"


def draw_rainfall(img, rainfall_status, icon_config, face_map):
    if not rainfall_status["raining"]["status"]:
        return img

    pos_x = 10
    pos_y = 70

    icon = my_lib.pil_util.load_image(icon_config)

    my_lib.pil_util.alpha_paste(
        img,
        icon,
        (pos_x, pos_y),
    )

    if rainfall_status["amount"] < 0.01:
        return img

    amount_text = gen_amount_text(rainfall_status["amount"])
    start_text = gen_start_text(rainfall_status["raining"]["start"])

    line_height = my_lib.pil_util.text_size(img, face_map["value"], "0")[1]

    pos_y = pos_y + icon.size[1] + 10

    next_pos_x = my_lib.pil_util.draw_text(
        img,
        amount_text,
        (pos_x, pos_y + line_height - my_lib.pil_util.text_size(img, face_map["value"], "0")[1]),
        face_map["value"],
        "left",
        "#333",
        stroke_width=10,
        stroke_fill=(255, 255, 255, 200),
    )[0]
    next_pos_x += my_lib.pil_util.text_size(img, face_map["unit"], " ")[0]
    next_pos_x = my_lib.pil_util.draw_text(
        img,
        "mm/h",
        (next_pos_x, pos_y + line_height - my_lib.pil_util.text_size(img, face_map["unit"], "h")[1]),
        face_map["unit"],
        "left",
        "#333",
        stroke_width=10,
        stroke_fill=(255, 255, 255, 200),
    )[0]
    next_pos_x += my_lib.pil_util.text_size(img, face_map["start"], " ")[0]

    pos_y = int(pos_y + line_height * 1.2)
    next_pos_x = my_lib.pil_util.draw_text(
        img,
        start_text,
        (pos_x, pos_y),
        face_map["start"],
        "left",
        "#333",
        stroke_width=10,
        stroke_fill=(255, 255, 255, 200),
    )[0]

    return img


def create_rain_fall_panel_impl(panel_config, font_config, db_config):
    face_map = get_face_map(font_config)

    img = PIL.Image.new(
        "RGBA",
        (panel_config["panel"]["width"], panel_config["panel"]["height"]),
        (255, 255, 255, 0),
    )

    status = get_rainfall_status(panel_config, db_config)

    if status is None:
        logging.warning("Unable to fetch rainfall status")
        return img

    draw_rainfall(img, status, panel_config["icon"], face_map)

    return img


def create(config):
    logging.info("draw rain cloud panel")

    start = time.perf_counter()

    panel_config = config["rain_fall"]
    font_config = config["font"]
    db_config = config["influxdb"]

    try:
        return (
            create_rain_fall_panel_impl(panel_config, font_config, db_config),
            time.perf_counter() - start,
        )
    except Exception:
        logging.exception("Failed to draw panel")

        error_message = traceback.format_exc()
        return (
            my_lib.panel_util.create_error_image(panel_config, font_config, error_message),
            time.perf_counter() - start,
            error_message,
        )


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    my_lib.logger.init("test", level=logging.INFO)

    config = my_lib.config.load(args["-c"])
    out_file = args["-o"]

    img = create(config)[0]

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
