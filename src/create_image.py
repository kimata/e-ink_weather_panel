#!/usr/bin/env python3
"""
電子ペーパ表示用の画像を生成します．

Usage:
  create_image.py [-c CONFIG] [-s] [-o PNG_FILE] [-t] [-D] [-d]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s           : 小型ディスプレイモードで実行します．
  -o PNG_FILE  : 生成した画像を指定されたパスに保存します．
  -t           : テストモードで実行します．
  -D           : ダミーモードで実行します．
  -d           : デバッグモード．
"""

import logging

# from concurrent import futures
import multiprocessing
import os
import pathlib
import sys
import textwrap
import time
import traceback

import PIL.Image
from docopt import docopt

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import my_lib.panel_util
import my_lib.pil_util
import weather_display.power_graph
import weather_display.rain_cloud_panel
import weather_display.sensor_graph
import weather_display.time_panel
import weather_display.wbgt_panel
import weather_display.weather_panel

# 一部の描画でエラー
ERROR_CODE_MINOR = 220
# 描画全体がエラー
ERROR_CODE_MAJOR = 222


def draw_wall(config, img):
    if "wall" not in config:
        return
    for wall_config in config["wall"]["image"]:
        my_lib.pil_util.alpha_paste(
            img,
            my_lib.pil_util.load_image(wall_config),
            (wall_config["offset_x"], wall_config["offset_y"]),
        )


def draw_panel(config, img, is_small_mode=False):
    if is_small_mode:
        panel_list = [
            {"name": "rain_cloud", "func": weather_display.rain_cloud_panel.create, "arg": (False,)},
            {"name": "weather", "func": weather_display.weather_panel.create, "arg": (False,)},
            {"name": "wbgt", "func": weather_display.wbgt_panel.create},
            {"name": "time", "func": weather_display.time_panel.create},
        ]
    else:
        panel_list = [
            {"name": "rain_cloud", "func": weather_display.rain_cloud_panel.create},
            {"name": "sensor", "func": weather_display.sensor_graph.create},
            {"name": "power", "func": weather_display.power_graph.create},
            {"name": "weather", "func": weather_display.weather_panel.create},
            {"name": "wbgt", "func": weather_display.wbgt_panel.create},
            {"name": "time", "func": weather_display.time_panel.create},
        ]

    panel_map = {}

    # NOTE: 並列処理 (matplotlib はマルチスレッド対応していないので，マルチプロセス処理する)
    start = time.perf_counter()
    pool = multiprocessing.Pool(processes=len(panel_list))
    for panel in panel_list:
        arg = (config,)
        if "arg" in panel:
            arg += panel["arg"]
        panel["task"] = pool.apply_async(panel["func"], arg)

    pool.close()
    pool.join()

    ret = 0
    for panel in panel_list:
        result = panel["task"].get()
        panel_img = result[0]
        elapsed = result[1]

        if len(result) > 2:
            my_lib.panel_util.notify_error(config, result[2])
            ret = ERROR_CODE_MINOR

        if "SCALE" in config[panel["name"]]["panel"]:
            panel_img = panel_img.resize(
                (
                    int(panel_img.size[0] * config[panel["name"]]["panel"]["scale"]),
                    int(panel_img.size[1] * config[panel["name"]]["panel"]["scale"]),
                ),
                PIL.Image.LANCZOS,
            )

        panel_map[panel["name"]] = panel_img

        logging.info("elapsed time: %s panel = %.3f sec", panel["name"], elapsed)
    logging.info("total elapsed time: %.3f sec", time.perf_counter() - start)

    draw_wall(config, img)

    for name in ["power", "weather", "sensor", "rain_cloud", "wbgt", "time"]:
        if name not in panel_map:
            continue

        my_lib.pil_util.alpha_paste(
            img,
            panel_map[name],
            (
                config[name]["panel"]["offset_x"],
                config[name]["panel"]["offset_y"],
            ),
        )

    return ret


def create_image(config, small_mode=False, dummy_mode=False, test_mode=False):
    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if dummy_mode:
        logging.warning("Set dummy mode")
        os.environ["DUMMY_MODE"] = "true"
    else:  # pragma: no cover
        pass

    logging.info("Start to create image")
    logging.info("Mode : %s", "small" if small_mode else "normal")

    img = PIL.Image.new(
        "RGBA",
        (config["panel"]["device"]["width"], config["panel"]["device"]["height"]),
        (255, 255, 255, 255),
    )
    if test_mode:
        return (img, 0)

    try:
        ret = draw_panel(config, img, small_mode)

        return (img, ret)
    except Exception:
        draw = PIL.ImageDraw.Draw(img)
        draw.rectangle(
            (
                0,
                0,
                config["panel"]["device"]["width"],
                config["panel"]["device"]["height"],
            ),
            fill=(255, 255, 255, 255),
        )

        my_lib.pil_util.draw_text(
            img,
            "ERROR",
            (10, 10),
            my_lib.pil_util.get_font(config["font"], "en_bold", 160),
            "left",
            "#666",
        )

        my_lib.pil_util.draw_text(
            img,
            "\n".join(textwrap.wrap(traceback.format_exc(), 100)),
            (20, 200),
            my_lib.pil_util.get_font(config["font"], "en_medium", 40),
            "left",
            "#333",
        )
        my_lib.panel_util.notify_error(config, traceback.format_exc())

        return (img, ERROR_CODE_MAJOR)


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    small_mode = args["-s"]
    dummy_mode = args["-D"]
    test_mode = args["-t"]
    debug_mode = args["-d"]

    log_level = logging.DEBUG if debug_mode else logging.INFO
    out_file = args["-o"] if args["-o"] is not None else sys.stdout.buffer

    my_lib.logger.init("panel.e-ink.weather", level=log_level)

    logging.info("Using config config: %s", config_file)
    config = my_lib.config.load(config_file)

    img, status = create_image(config, small_mode, dummy_mode, test_mode)

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    if status == 0:
        logging.info("create_image: Succeeded.")
    else:
        logging.warning("create_image: Something wrong..")

    logging.info("Finish.")

    sys.exit(status)
