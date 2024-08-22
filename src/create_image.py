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

import logger
import power_graph
import rain_cloud_panel
import sensor_graph
import time_panel
import wbgt_panel
import weather_panel
from config import load_config
from panel_util import notify_error
from pil_util import alpha_paste, convert_to_gray, draw_text, get_font, load_image

# 一部の描画でエラー
ERROR_CODE_MINOR = 220
# 描画全体がエラー
ERROR_CODE_MAJOR = 222


def draw_wall(config, img):
    if "WALL" not in config:
        return
    for wall_config in config["WALL"]["IMAGE"]:
        alpha_paste(
            img,
            load_image(wall_config),
            (wall_config["OFFSET_X"], wall_config["OFFSET_Y"]),
        )


def draw_panel(config, img, is_small_mode=False):
    if is_small_mode:
        panel_list = [
            {"name": "RAIN_CLOUD", "func": rain_cloud_panel.create, "arg": (False,)},
            {"name": "WEATHER", "func": weather_panel.create, "arg": (False,)},
            {"name": "WBGT", "func": wbgt_panel.create},
            {"name": "TIME", "func": time_panel.create},
        ]
    else:
        panel_list = [
            {"name": "RAIN_CLOUD", "func": rain_cloud_panel.create},
            {"name": "SENSOR", "func": sensor_graph.create},
            {"name": "POWER", "func": power_graph.create},
            {"name": "WEATHER", "func": weather_panel.create},
            {"name": "WBGT", "func": wbgt_panel.create},
            {"name": "TIME", "func": time_panel.create},
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
            notify_error(config, result[2])
            ret = ERROR_CODE_MINOR

        if "SCALE" in config[panel["name"]]["PANEL"]:
            panel_img = panel_img.resize(
                (
                    int(panel_img.size[0] * config[panel["name"]]["PANEL"]["SCALE"]),
                    int(panel_img.size[1] * config[panel["name"]]["PANEL"]["SCALE"]),
                ),
                PIL.Image.LANCZOS,
            )

        panel_map[panel["name"]] = panel_img

        logging.info("elapsed time: %s panel = %.3f sec", panel["name"], elapsed)
    logging.info("total elapsed time: %.3f sec", time.perf_counter() - start)

    draw_wall(config, img)

    for name in ["POWER", "WEATHER", "SENSOR", "RAIN_CLOUD", "WBGT", "TIME"]:
        if name not in panel_map:
            continue

        alpha_paste(
            img,
            panel_map[name],
            (
                config[name]["PANEL"]["OFFSET_X"],
                config[name]["PANEL"]["OFFSET_Y"],
            ),
        )

    return ret


def create_image(config_file, small_mode=False, dummy_mode=False, test_mode=False, debug_mode=False):
    log_level = logging.DEBUG if debug_mode else logging.INFO

    logger.init("panel.e-ink.weather", level=log_level)

    # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
    if dummy_mode:
        logging.warning("Set dummy mode")
        os.environ["DUMMY_MODE"] = "true"
    else:  # pragma: no cover
        pass

    logging.info("Start to create image")

    logging.info("Using config config: {config_file}".format(config_file=config_file))
    config = load_config(config_file)

    logging.info("Mode : {mode}".format(mode="small" if small_mode else "normal"))

    img = PIL.Image.new(
        "RGBA",
        (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
        (255, 255, 255, 255),
    )
    if test_mode:
        return (img, 0)

    try:
        ret = draw_panel(config, img, small_mode)

        return (img, ret)
    except:
        draw = PIL.ImageDraw.Draw(img)
        draw.rectangle(
            (
                0,
                0,
                config["PANEL"]["DEVICE"]["WIDTH"],
                config["PANEL"]["DEVICE"]["HEIGHT"],
            ),
            fill=(255, 255, 255, 255),
        )

        draw_text(
            img,
            "ERROR",
            (10, 10),
            get_font(config["FONT"], "EN_BOLD", 160),
            "left",
            "#666",
        )

        draw_text(
            img,
            "\n".join(textwrap.wrap(traceback.format_exc(), 100)),
            (20, 200),
            get_font(config["FONT"], "EN_MEDIUM", 40),
            "left" "#333",
        )
        notify_error(config, traceback.format_exc())

        return (img, ERROR_CODE_MAJOR)


######################################################################
if __name__ == "__main__":
    args = docopt(__doc__)

    config_file = args["-c"]
    small_mode = args["-s"]
    dummy_mode = args["-D"]
    test_mode = args["-t"]
    debug_mode = args["-d"]

    img, status = create_image(config_file, small_mode, dummy_mode, test_mode, debug_mode)

    if args["-o"] is not None:
        out_file = args["-o"]
    else:
        out_file = sys.stdout.buffer

    logging.info("Save {out_file}.".format(out_file=str(out_file)))
    convert_to_gray(img).save(out_file, "PNG")

    if status == 0:
        logging.info("create_image: Succeeded.")
    else:
        logging.warning("create_image: Something wrong..")

    exit(status)
