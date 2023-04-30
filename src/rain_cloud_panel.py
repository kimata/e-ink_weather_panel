#!/usr/bin/env python3
# - coding: utf-8 --
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import PIL.Image
import PIL.ImageDraw

import datetime
import cv2
import numpy as np
import time
import logging

from webdriver import create_driver
from pil_util import get_font, draw_text

CLOUD_IMAGE_XPATH = '//div[contains(@id, "jmatile_map_")]'


def get_face_map(font_config):
    return {
        "title": get_font(font_config, "JP_MEDIUM", 50),
    }


def shape_cloud_display(driver, parts_list, width, height, is_future):
    SCRIPT_CHANGE_DISPAY = """
var elements = document.getElementsByClassName("{class_name}")
    for (i = 0; i < elements.length; i++) {{
        elements[i].style.display="{mode}"
    }}
"""
    # driver.find_element(By.XPATH, '//a[contains(@aria-label, "地形を表示")]').click()

    driver.find_element(By.XPATH, '//a[contains(@aria-label, "色の濃さ")]').click()
    driver.find_element(By.XPATH, '//span[contains(text(), "濃い")]').click()

    driver.find_element(By.XPATH, '//a[contains(@aria-label, "地図を切り替え")]').click()
    driver.find_element(By.XPATH, '//span[contains(text(), "地名なし")]').click()

    for parts in parts_list:
        driver.execute_script(
            SCRIPT_CHANGE_DISPAY.format(
                class_name=parts["class"],
                mode=parts["mode"],
            )
        )

    if is_future:
        driver.find_element(
            By.XPATH,
            '//div[@class="jmatile-control"]//div[contains(text(), " +1時間 ")]',
        ).click()


def change_window_size(driver, url, width, height):
    wait = WebDriverWait(driver, 5)

    # NOTE: 雨雲画像がこのサイズになるように，ウィンドウサイズを調整する
    logging.info("target: {width} x {height}".format(width=width, height=height))

    driver.get(url)
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))

    # NOTE: まずはサイズを大きめにしておく
    driver.set_window_size(int(height * 2), int(height * 1.5))
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))

    # NOTE: 最初に横サイズを調整
    window_size = driver.get_window_size()
    element_size = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[current] window: {window_width} x {window_height}, element: {element_width} x {element_height}".format(
            window_width=window_size["width"],
            window_height=window_size["height"],
            element_width=element_size["width"],
            element_height=element_size["height"],
        )
    )
    if element_size["width"] != width:
        target_window_width = window_size["width"] + (width - element_size["width"])
        logging.info(
            "[change] window: {window_width} x {window_height}".format(
                window_width=target_window_width,
                window_height=window_size["height"],
            )
        )
        driver.set_window_size(target_window_width, height)
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))

    # NOTE: 次に縦サイズを調整
    window_size = driver.get_window_size()
    element_size = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[current] window: {window_width} x {window_height}, element: {element_width} x {element_height}".format(
            window_width=window_size["width"],
            window_height=window_size["height"],
            element_width=element_size["width"],
            element_height=element_size["height"],
        )
    )
    if element_size["height"] != height:
        target_window_height = window_size["height"] + (height - element_size["height"])
        logging.info(
            "[change] window: {window_width} x {window_height}".format(
                window_width=window_size["width"],
                window_height=target_window_height,
            )
        )
        driver.set_window_size(
            window_size["width"],
            target_window_height,
        )
    driver.refresh()
    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))
    time.sleep(0.5)

    window_size = driver.get_window_size()
    element_size = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[current] window: {window_width} x {window_height}, element: {element_width} x {element_height}".format(
            window_width=window_size["width"],
            window_height=window_size["height"],
            element_width=element_size["width"],
            element_height=element_size["height"],
        )
    )
    logging.info(
        "size is {status}".format(
            status="OK"
            if (element_size["width"], element_size["height"]) == (width, height)
            else "NG"
        )
    )


def fetch_cloud_image(driver, url, width, height, is_future=False):
    PARTS_LIST = [
        {"class": "jmatile-map-title", "mode": "none"},
        {"class": "leaflet-bar", "mode": "none"},
        {"class": "leaflet-control-attribution", "mode": "none"},
        {"class": "leaflet-control-scale-line", "mode": "none"},
    ]

    wait = WebDriverWait(driver, 5)

    driver.get(url)

    wait.until(EC.presence_of_element_located((By.XPATH, CLOUD_IMAGE_XPATH)))
    for parts in PARTS_LIST:
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, parts["class"])))

    shape_cloud_display(driver, PARTS_LIST, width, height, is_future)

    wait.until(
        lambda driver: driver.execute_script("return document.readyState") == "complete"
    )
    time.sleep(0.5)

    png_data = driver.find_element(By.XPATH, CLOUD_IMAGE_XPATH).screenshot_as_png
    driver.refresh()

    return png_data


def retouch_cloud_image(png_data):
    RAINFALL_INTENSITY_LEVEL = [
        # NOTE: 白
        {"func": lambda h, s: (160 < h) & (h < 180) & (s < 20)},
        # NOTE: 薄水色
        {"func": lambda h, s: (140 < h) & (h < 150) & (90 < s) & (s < 100)},
        # NOTE: 水色
        {"func": lambda h, s: (145 < h) & (h < 155) & (210 < s) & (s < 230)},
        # NOTE: 青色
        {"func": lambda h, s: (155 < h) & (h < 165) & (230 < s)},
        # NOTE: 黄色
        {"func": lambda h, s: (35 < h) & (h < 45)},
        # NOTE: 橙色
        {"func": lambda h, s: (20 < h) & (h < 30)},
        # NOTE: 赤色
        {"func": lambda h, s: (0 < h) & (h < 8)},
        # NOTE: 紫色
        {"func": lambda h, s: (225 < h) & (h < 235) & (240 < s)},
    ]

    img_rgb = cv2.imdecode(
        np.asarray(bytearray(png_data), dtype=np.uint8), cv2.IMREAD_COLOR
    )

    img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2HSV_FULL).astype(np.float32)
    h, s, v = cv2.split(img_hsv)

    # NOTE: 降雨強度の色をグレースケール用に変換
    for i, level in enumerate(RAINFALL_INTENSITY_LEVEL):
        img_hsv[level["func"](h, s), 0] = 0
        img_hsv[level["func"](h, s), 1] = 80
        img_hsv[level["func"](h, s), 2] = 256 / 16 * (16 - i * 2)

    # NOTE: 白地図の色をやや明るめにする
    img_hsv[s < 30, 2] = np.clip(pow(v[(s < 30)], 1.35) * 0.3, 0, 255)

    return PIL.Image.fromarray(
        cv2.cvtColor(
            cv2.cvtColor(img_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB_FULL),
            cv2.COLOR_RGB2RGBA,
        )
    )


def draw_equidistant_circle(img):
    draw = PIL.ImageDraw.Draw(img)
    x = img.size[0] / 2
    y = img.size[1] / 2

    size = 20
    draw.ellipse(
        (x - size / 2, y - size / 2, x + size / 2, y + size / 2),
        fill=(255, 255, 255),
        outline=(60, 60, 60),
        width=5,
    )
    # 5km
    size = 327
    draw.ellipse(
        (x - size / 2, y - size / 2, x + size / 2, y + size / 2),
        outline=(255, 255, 255),
        width=16,
    )
    size = 322
    draw.ellipse(
        (x - size / 2, y - size / 2, x + size / 2, y + size / 2),
        outline=(160, 160, 160),
        width=10,
    )

    return img


def draw_caption(img, title, face):
    size = face["title"].getsize(title)
    x = 10
    y = 10
    padding = 12
    radius = 20
    alpha = 200

    overlay = PIL.Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = PIL.ImageDraw.Draw(overlay)
    draw.rectangle(
        (
            x - padding,
            y - padding,
            x + size[0] + padding - radius,
            y + size[1] + padding,
        ),
        fill=(255, 255, 255, alpha),
    )
    draw.rectangle(
        (x - padding, y - padding, x + size[0] + padding, y + padding),
        fill=(255, 255, 255, alpha),
    )

    draw.rounded_rectangle(
        (x - padding, y - padding, x + size[0] + padding, y + size[1] + padding),
        fill=(255, 255, 255, alpha),
        radius=radius,
    )
    img = PIL.Image.alpha_composite(img, overlay)
    draw_text(
        img,
        title,
        [10, 10],
        face["title"],
        "left",
        color="#000",
    )

    return img


def create_rain_cloud_panel(config):
    panel_config = config["RAIN_CLOUD"]
    font_config = config["FONT"]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9), "JST"))

    SUB_PANEL_CONFIG_LIST = [
        {"is_future": False, "title": now.strftime("現在 (%H:%M)"), "offset_x": 0},
        {
            "is_future": True,
            "title": "１時間後",
            "offset_x": int(panel_config["PANEL"]["WIDTH"] / 2),
        },
    ]
    driver = create_driver()

    change_window_size(
        driver,
        panel_config["DATA"]["JMA"]["URL"],
        int(panel_config["PANEL"]["WIDTH"] / 2),
        panel_config["PANEL"]["HEIGHT"],
    )

    img = PIL.Image.new(
        "RGBA",
        (panel_config["PANEL"]["WIDTH"], panel_config["PANEL"]["HEIGHT"]),
        (255, 255, 255, 255),
    )
    face_map = get_face_map(font_config)

    for sub_panel_config in SUB_PANEL_CONFIG_LIST:
        sub_img = retouch_cloud_image(
            fetch_cloud_image(
                driver,
                panel_config["DATA"]["JMA"]["URL"],
                int(panel_config["PANEL"]["WIDTH"] / 2),
                panel_config["PANEL"]["HEIGHT"],
                sub_panel_config["is_future"],
            )
        )
        time.sleep(1)
        sub_img = draw_equidistant_circle(sub_img)
        sub_img = draw_caption(sub_img, sub_panel_config["title"], face_map)
        img.paste(sub_img, (sub_panel_config["offset_x"], 0))

    driver.quit()

    return img.convert("L")


if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test")
    logging.info("Test")

    config = load_config()

    img = create_rain_cloud_panel(config)

    img.save("test_rain_cloud_panel.png", "PNG")

    print("Finish.")
