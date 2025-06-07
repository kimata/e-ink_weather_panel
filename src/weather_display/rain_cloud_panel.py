#!/usr/bin/env python3
"""
雨雲レーダー画像を生成します。

Usage:
  rain_cloud_panel.py [-c CONFIG] -o PNG_FILE [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -o PNG_FILE       : 生成した画像を指定されたパスに保存します。
  -D                : デバッグモードで動作します。
"""

import concurrent
import io
import logging
import pathlib
import pickle
import time
import traceback

import cv2
import my_lib.notify.slack
import my_lib.panel_util
import my_lib.pil_util
import my_lib.thread_util
import numpy  # noqa: ICN001
import PIL.Image
import PIL.ImageDraw
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.wait
from my_lib.selenium_util import click_xpath  # NOTE: テスト時に mock する

DATA_PATH = pathlib.Path("data")
WINDOW_SIZE_CACHE_FILE = DATA_PATH / "window_size_cache.dat"

CLOUD_IMAGE_XPATH = '//div[contains(@id, "jmatile_map_")]'

RAINFALL_INTENSITY_LEVEL = [
    # NOTE: 白
    {"func": lambda h, s: (160 < h) & (h < 180) & (s < 20), "value": 1},  # noqa: SIM300
    # NOTE: 薄水色
    {"func": lambda h, s: (140 < h) & (h < 150) & (90 < s) & (s < 100), "value": 5},  # noqa: SIM300
    # NOTE: 水色
    {"func": lambda h, s: (145 < h) & (h < 155) & (210 < s) & (s < 230), "value": 10},  # noqa: SIM300
    # NOTE: 青色
    {"func": lambda h, s: (155 < h) & (h < 165) & (230 < s), "value": 20},  # noqa: SIM300
    # NOTE: 黄色
    {"func": lambda h, s: (35 < h) & (h < 45), "value": 30},  # noqa: SIM300, ARG005
    # NOTE: 橙色
    {"func": lambda h, s: (20 < h) & (h < 30), "value": 50},  # noqa: SIM300, ARG005
    # NOTE: 赤色
    {"func": lambda h, s: (0 < h) & (h < 8), "value": 80},  # noqa: SIM300, ARG005
    # NOTE: 紫色
    {"func": lambda h, s: (225 < h) & (h < 235) & (240 < s)},  # noqa: SIM300
]


def get_face_map(font_config):
    return {
        "title": my_lib.pil_util.get_font(font_config, "jp_medium", 50),
        "legend": my_lib.pil_util.get_font(font_config, "en_medium", 30),
        "legend_unit": my_lib.pil_util.get_font(font_config, "en_medium", 18),
    }


def hide_label_and_icon(driver, wait):
    PARTS_LIST = [
        {"class": "jmatile-map-title", "mode": "none"},
        {"class": "leaflet-bar", "mode": "none"},
        {"class": "leaflet-control-attribution", "mode": "none"},
        {"class": "leaflet-control-scale-line", "mode": "none"},
    ]
    SCRIPT_CHANGE_DISPAY = """
var elements = document.getElementsByClassName("{class_name}")
    for (i = 0; i < elements.length; i++) {{
        elements[i].style.display="{mode}"
    }}
"""

    for parts in PARTS_LIST:
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.CLASS_NAME, parts["class"])
            )
        )

    for parts in PARTS_LIST:
        driver.execute_script(
            SCRIPT_CHANGE_DISPAY.format(
                class_name=parts["class"],
                mode=parts["mode"],
            )
        )


def change_setting(driver, wait):
    # driver.find_element(
    #     selenium.webdriver.common.by.By.XPATH, '//a[contains(@aria-label, "地形を表示")]'
    # ).click()

    click_xpath(
        driver,
        '//a[contains(@aria-label, "色の濃さ")]',
        wait,
        True,
    )
    click_xpath(
        driver,
        '//span[contains(text(), "濃い")]',
        wait,
        True,
    )
    click_xpath(
        driver,
        '//a[contains(@aria-label, "地図を切り替え")]',
        wait,
        True,
    )
    click_xpath(
        driver,
        '//span[contains(text(), "地名なし")]',
        wait,
        True,
    )


def shape_cloud_display(driver, wait, width, height, is_future):  # noqa: ARG001
    if is_future:
        click_xpath(
            driver,
            '//div[@class="jmatile-control"]//div[contains(text(), " +1時間 ")]',
            wait,
            True,
        )

    change_setting(driver, wait)
    hide_label_and_icon(driver, wait)


def load_window_size_cache():
    """ウィンドウサイズキャッシュを読み込む"""
    try:
        if WINDOW_SIZE_CACHE_FILE.exists():
            with WINDOW_SIZE_CACHE_FILE.open("rb") as f:
                return pickle.load(f)  # noqa: S301
    except Exception:
        logging.warning("Failed to load window size cache")
    return {}


def save_window_size_cache(cache):
    """ウィンドウサイズキャッシュを保存する"""
    try:
        WINDOW_SIZE_CACHE_FILE.parent.mkdir(exist_ok=True)
        with WINDOW_SIZE_CACHE_FILE.open("wb") as f:
            pickle.dump(cache, f)
    except Exception:
        logging.warning("Failed to save window size cache")


def change_window_size_fallback(driver, width, height):
    """従来のウィンドウサイズ調整ロジック（フォールバック用）"""
    logging.info("Using fallback window size adjustment")

    # NOTE: まずはサイズを大きめにしておく
    driver.set_window_size(int(height * 2), int(height * 1.5))
    time.sleep(1)

    # NOTE: 最初に横サイズを調整
    window_size = driver.get_window_size()
    element_size = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[actual] window: %d x %d, element: %d x %d",
        window_size["width"],
        window_size["height"],
        element_size["width"],
        element_size["height"],
    )

    if element_size["width"] != width:
        target_window_width = window_size["width"] + (width - element_size["width"])
        logging.info("[change] window: %d x %d", target_window_width, window_size["height"])
        driver.set_window_size(target_window_width, height)
        time.sleep(1)

    # NOTE: 次に縦サイズを調整
    window_size = driver.get_window_size()
    element_size = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[actual] window: %d x %d, element: %d x %d",
        window_size["width"],
        window_size["height"],
        element_size["width"],
        element_size["height"],
    )
    if element_size["height"] != height:
        target_window_height = window_size["height"] + (height - element_size["height"])
        logging.info("[change] window: %d x %d", window_size["width"], target_window_height)
        driver.set_window_size(
            window_size["width"],
            target_window_height,
        )
        time.sleep(1)

    final_window_size = driver.get_window_size()
    element_size = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).size
    logging.info(
        "[final] window: %d x %d, element: %d x %d",
        final_window_size["width"],
        final_window_size["height"],
        element_size["width"],
        element_size["height"],
    )

    return final_window_size


def change_window_size(driver, width, height):
    """最適化されたウィンドウサイズ調整（キャッシュ使用+フォールバック）"""
    logging.info("target: %d x %d", width, height)

    cache_key = f"{width}x{height}"
    cache = load_window_size_cache()

    if cache_key in cache:
        # キャッシュから最適なウィンドウサイズを取得して一発設定
        cached_window_size = cache[cache_key]
        logging.info(
            "Using cached window size: %d x %d",
            cached_window_size["width"],
            cached_window_size["height"],
        )
        driver.set_window_size(cached_window_size["width"], cached_window_size["height"])
        time.sleep(1)  # 短い待機時間

        # 結果を確認
        element_size = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).size
        tolerance = 5  # 許容誤差

        if (
            abs(element_size["width"] - width) <= tolerance
            and abs(element_size["height"] - height) <= tolerance
        ):
            logging.info("Cached window size worked correctly")
            return driver.get_window_size()
        else:
            logging.info("Cached window size failed, falling back to adjustment logic")

    # キャッシュが無いか失敗した場合はフォールバック
    final_window_size = change_window_size_fallback(driver, width, height)

    # 成功した場合はキャッシュに保存
    element_size = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).size
    if (element_size["width"], element_size["height"]) == (width, height):
        cache[cache_key] = final_window_size
        save_window_size_cache(cache)
        logging.info("Saved window size to cache: %s -> %s", cache_key, final_window_size)

    logging.info(
        "size is %s",
        "OK" if (element_size["width"], element_size["height"]) == (width, height) else "unmatch",
    )

    return final_window_size


def fetch_cloud_image(driver, wait, url, width, height, is_future=False):  # noqa: PLR0913
    logging.info("fetch cloud image")

    driver.get(url)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH)
        )
    )

    change_window_size(driver, width, height)
    shape_cloud_display(driver, wait, width, height, is_future)

    wait.until(lambda driver: driver.execute_script("return document.readyState") == "complete")
    time.sleep(0.5)

    png_data = driver.find_element(selenium.webdriver.common.by.By.XPATH, CLOUD_IMAGE_XPATH).screenshot_as_png

    driver.refresh()

    return png_data


def retouch_cloud_image(png_data, panel_config):
    logging.info("retouch image")

    # より効率的なデコード
    img_array = numpy.frombuffer(png_data, dtype=numpy.uint8)
    img_rgb = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_BGR2HSV_FULL).astype(numpy.float32)
    bar = numpy.zeros((1, len(RAINFALL_INTENSITY_LEVEL), 3), dtype=numpy.uint8)
    h, s, v = cv2.split(img_hsv)

    # 事前計算で高速化
    gamma = panel_config["legend"]["gamma"]
    level_count = len(RAINFALL_INTENSITY_LEVEL)

    # NOTE: 降雨強度の色をグレースケール用に変換
    for i, level in enumerate(RAINFALL_INTENSITY_LEVEL):
        intensity = (float(level_count - i) / level_count) ** gamma
        color = (0, 80, int(255 * intensity))

        # マスクを事前計算して適用
        mask = level["func"](h, s)
        img_hsv[mask] = color
        bar[0, i] = color

    # 白地図処理を最適化
    white_mask = s < 30
    if numpy.any(white_mask):
        img_hsv[white_mask, 2] = numpy.clip(numpy.power(v[white_mask], 1.35) * 0.3, 0, 255)

    # 色変換を1回に削減
    img_rgb = cv2.cvtColor(img_hsv.astype(numpy.uint8), cv2.COLOR_HSV2RGB_FULL)
    img_rgba = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2RGBA)
    bar_rgb = cv2.cvtColor(bar, cv2.COLOR_HSV2RGB_FULL)
    bar_rgba = cv2.cvtColor(bar_rgb, cv2.COLOR_RGB2RGBA)

    return (
        PIL.Image.fromarray(img_rgba),
        PIL.Image.fromarray(bar_rgba),
    )


def draw_equidistant_circle(img):
    logging.info("draw equidistant_circle")
    draw = PIL.ImageDraw.Draw(img)
    center_x = img.size[0] // 2
    center_y = img.size[1] // 2

    # 一括で円を描画（定数を事前定義）
    circles = [
        (20, (255, 255, 255), (60, 60, 60), 5),  # 中心点（塗りつぶしあり）
        (328, None, (255, 255, 255), 16),  # 5km 外側（輪郭のみ）
        (322, None, (180, 180, 180), 10),  # 5km 内側（輪郭のみ）
    ]

    for size, fill, outline, width in circles:
        half_size = size // 2
        bbox = (center_x - half_size, center_y - half_size, center_x + half_size, center_y + half_size)
        draw.ellipse(bbox, fill=fill, outline=outline, width=width)

    return img


def draw_caption(img, title, face_map):
    logging.info("draw caption")
    caption_size = my_lib.pil_util.text_size(img, face_map["title"], title)
    caption_size = (caption_size[0] + 5, caption_size[1])  # NOTE: 横方向を少し広げる

    # 定数を事前定義
    x, y = 12, 12
    padding = 10
    radius = 20
    alpha = 200
    half_padding = padding // 2

    # オーバーレイサイズを最小限に
    overlay_width = caption_size[0] + padding * 2
    overlay_height = caption_size[1] + padding + half_padding
    overlay = PIL.Image.new("RGBA", (overlay_width, overlay_height), (255, 255, 255, 0))
    draw = PIL.ImageDraw.Draw(overlay)

    # 角丸長方形を一度で描画
    draw.rounded_rectangle(
        (0, 0, overlay_width, overlay_height),
        fill=(255, 255, 255, alpha),
        radius=radius,
    )

    # オーバーレイを元画像に貼り付け
    img.paste(overlay, (x - padding, y - padding), overlay)

    # テキストを直接描画
    my_lib.pil_util.draw_text(
        img,
        title,
        (x, y),
        face_map["title"],
        "left",
        color="#000",
    )

    return img


def create_rain_cloud_img(panel_config, sub_panel_config, face_map, slack_config, trial):
    logging.info("create rain cloud image (%s)", "future" if sub_panel_config["is_future"] else "current")

    driver = my_lib.selenium_util.create_driver(
        "rain_cloud" + ("_future" if sub_panel_config["is_future"] else ""), DATA_PATH
    )

    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

    my_lib.selenium_util.clear_cache(driver)

    img = None
    try:
        img = fetch_cloud_image(
            driver,
            wait,
            panel_config["data"]["jma"]["url"],
            sub_panel_config["width"],
            sub_panel_config["height"],
            sub_panel_config["is_future"],
        )
    except Exception:
        if (trial >= 3) and (slack_config is not None):
            my_lib.notify.slack.error_with_image(
                slack_config["bot_token"],
                slack_config["error"]["channel"]["name"],
                slack_config["error"]["channel"]["id"],
                slack_config["from"],
                traceback.format_exc(),
                {
                    "data": PIL.Image.open(io.BytesIO(driver.get_screenshot_as_png())),
                    "text": "エラー時のスクリーンショット",
                },
                interval_min=slack_config["error"]["interval_min"],
            )
        driver.quit()

        # NOTE: リトライまでに時間を空けるようにする
        time.sleep(10)

        raise

    driver.quit()

    img, bar = retouch_cloud_image(img, panel_config)
    img = draw_equidistant_circle(img)
    img = draw_caption(img, sub_panel_config["title"], face_map)

    return (img, bar)


def draw_legend(img, bar, panel_config, face_map):
    PADDING = 20

    bar_size = panel_config["legend"]["bar_size"]
    bar = bar.resize(
        (
            bar.size[0] * bar_size,
            bar.size[1] * bar_size,
        ),
        PIL.Image.NEAREST,
    )
    draw = PIL.ImageDraw.Draw(bar)
    for i in range(len(RAINFALL_INTENSITY_LEVEL)):
        draw.rectangle(
            (
                max(bar_size * i - 1, 0),
                0,
                bar_size * (i + 1) - 1,
                bar_size - 1,
            ),
            outline=(20, 20, 20),
        )

    text_height = int(my_lib.pil_util.text_size(img, face_map["legend"], "0")[1])
    unit = "mm/h"
    unit_width, unit_height = my_lib.pil_util.text_size(img, face_map["legend_unit"], unit)
    unit_overlap = my_lib.pil_util.text_size(img, face_map["legend_unit"], unit[0])[0]
    legend = PIL.Image.new(
        "RGBA",
        (
            bar.size[0] + PADDING * 2 + unit_width - unit_overlap,
            bar.size[1] + PADDING * 2 + text_height,
        ),
        (255, 255, 255, 0),
    )
    draw = PIL.ImageDraw.Draw(legend)
    draw.rounded_rectangle(
        (0, 0, legend.size[0], legend.size[1]),
        radius=8,
        fill=(255, 255, 255, 200),
    )

    legend.paste(bar, (PADDING, PADDING + text_height))
    for i in range(len(RAINFALL_INTENSITY_LEVEL)):
        if "value" in RAINFALL_INTENSITY_LEVEL[i]:
            text = str(RAINFALL_INTENSITY_LEVEL[i]["value"])
            pos_x = PADDING + bar_size * (i + 1)
            pos_y = PADDING - 5
            align = "center"
            font = face_map["legend"]
        else:
            text = "mm/h"
            pos_x = PADDING + bar_size * (i + 1) - unit_overlap
            pos_y = PADDING - 5 + my_lib.pil_util.text_size(img, face_map["legend"], "0")[1] - unit_height
            align = "left"
            font = face_map["legend_unit"]

        my_lib.pil_util.draw_text(
            legend,
            text,
            (
                pos_x,
                pos_y,
            ),
            font,
            align,
            "#666",
        )

    my_lib.pil_util.alpha_paste(
        img,
        legend,
        (panel_config["legend"]["offset_x"], panel_config["legend"]["offset_y"] - 80),
    )

    return img


def create_rain_cloud_panel_impl(  # noqa: PLR0913
    panel_config,
    font_config,
    slack_config,
    is_side_by_side,
    trial,
    is_threaded=True,
):
    if is_side_by_side:
        sub_width = int(panel_config["panel"]["width"] / 2)
        sub_height = panel_config["panel"]["height"]
        offset_x = int(panel_config["panel"]["width"] / 2)
        offset_y = 0
    else:
        sub_width = panel_config["panel"]["width"]
        sub_height = int(panel_config["panel"]["height"] / 2)
        offset_x = 0
        offset_y = int(panel_config["panel"]["height"] / 2)

    SUB_PANEL_CONFIG_LIST = [
        {
            "is_future": False,
            "title": "現在",
            "width": sub_width,
            "height": sub_height,
            "offset_x": 0,
            "offset_y": 0,
        },
        {
            "is_future": True,
            "title": "１時間後",
            "width": sub_width,
            "height": sub_height,
            "offset_x": offset_x,
            "offset_y": offset_y,
        },
    ]

    img = PIL.Image.new(
        "RGBA",
        (panel_config["panel"]["width"], panel_config["panel"]["height"]),
        (255, 255, 255, 255),
    )
    face_map = get_face_map(font_config)

    executor = (
        concurrent.futures.ThreadPoolExecutor(len(SUB_PANEL_CONFIG_LIST))
        if is_threaded
        else my_lib.thread_util.SingleThreadExecutor()
    )

    task_list = [
        executor.submit(
            create_rain_cloud_img,
            panel_config,
            sub_panel_config,
            face_map,
            slack_config,
            trial,
        )
        for sub_panel_config in SUB_PANEL_CONFIG_LIST
    ]

    for i, sub_panel_config in enumerate(SUB_PANEL_CONFIG_LIST):
        sub_img, bar = task_list[i].result()
        img.paste(sub_img, (sub_panel_config["offset_x"], sub_panel_config["offset_y"]))

    executor.shutdown(True)

    return draw_legend(img, bar, panel_config, face_map)


def create(config, is_side_by_side=True, is_threaded=True):
    logging.info("draw rain cloud panel")

    return my_lib.panel_util.draw_panel_patiently(
        create_rain_cloud_panel_impl,
        config["rain_cloud"],
        config["font"],
        config.get("slack", None),
        is_side_by_side,
        is_threaded,
    )


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    out_file = args["-o"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    img = create_rain_cloud_panel_impl(config["rain_cloud"], config["font"], None, True, 1)

    logging.info("Save %s.", out_file)
    my_lib.pil_util.convert_to_gray(img).save(out_file, "PNG")

    logging.info("Finish.")
