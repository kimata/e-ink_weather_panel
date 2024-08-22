#!/usr/bin/env python3
"""
時刻の画像を生成します．

Usage:
  time_panel.py [-c CONFIG] -o PNG_FILE

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
"""

import datetime
import logging
import time

import my_lib.pil_util
import PIL.Image
import PIL.ImageDraw
import PIL.ImageEnhance
import PIL.ImageFont


def get_face_map(font_config):
    return {
        "time": {
            "value": my_lib.pil_util.get_font(font_config, "en_bold", 130),
        },
    }


def draw_time(img, pos_x, pos_y, face):
    time_text = (
        datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), "JST"))
        + datetime.timedelta(minutes=1)
    ).strftime("%H:%M")

    pos_y -= my_lib.pil_util.text_size(img, face["value"], time_text)[1]
    pos_x += 10

    my_lib.pil_util.draw_text(
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
    panel_config = config["time"]
    font_config = config["font"]

    face_map = get_face_map(font_config)

    # 右下に描画する
    draw_time(
        img,
        panel_config["panel"]["width"] - 10,
        panel_config["panel"]["height"] - 10,
        face_map["time"],
    )


def create(config):
    logging.info("draw time panel")
    start = time.perf_counter()

    img = PIL.Image.new(
        "RGBA",
        (config["time"]["panel"]["width"], config["time"]["panel"]["height"]),
        (255, 255, 255, 0),
    )

    draw_panel_time(img, config)

    return (img, time.perf_counter() - start)


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
