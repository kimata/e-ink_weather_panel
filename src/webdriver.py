#!/usr/bin/env python3
# - coding: utf-8 --

import os
import pathlib
import shutil
import inspect
import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.utils import ChromeType

DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"
LOG_PATH = DATA_PATH / "log"

CHROME_DATA_PATH = str(DATA_PATH / "chrome")
DUMP_PATH = str(DATA_PATH / "deubg")

DRIVER_LOG_PATH = str(LOG_PATH / "webdriver.log")


def create_driver():
    pathlib.Path(CHROME_DATA_PATH).mkdir(parents=True, exist_ok=True)
    pathlib.Path(LOG_PATH).mkdir(parents=True, exist_ok=True)
    pathlib.Path(DUMP_PATH).mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")  # for Docker
    options.add_argument("--disable-dev-shm-usage")  # for Docker

    options.add_argument("--lang=ja-JP")
    options.add_argument("--window-size=1920,1080")

    options.add_argument(
        '--user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36"'
    )
    options.add_argument("--user-data-dir=" + CHROME_DATA_PATH)

    # NOTE: 下記がないと，snap で入れた chromium が「LC_ALL: cannot change locale (ja_JP.UTF-8)」
    # と出力し，その結果 ChromeDriverManager がバージョンを正しく取得できなくなる
    os.environ["LC_ALL"] = "C"

    if shutil.which("google-chrome") is not None:
        chrome_type = ChromeType.GOOGLE
    else:
        chrome_type = ChromeType.CHROMIUM

    driver = webdriver.Chrome(
        service=Service(
            ChromeDriverManager(chrome_type=chrome_type).install(),
            log_path=DRIVER_LOG_PATH,
            service_args=["--verbose"],
        ),
        options=options,
    )

    return driver


def dump_page(driver, index, dump_path=DUMP_PATH):
    name = inspect.stack()[1].function.replace("<", "").replace(">", "")
    dump_path = pathlib.Path(dump_path)

    os.makedirs(str(dump_path), exist_ok=True)

    png_path = dump_path / (
        "{name}_{index:02d}.{ext}".format(name=name, index=index, ext="png")
    )
    htm_path = dump_path / (
        "{name}_{index:02d}.{ext}".format(name=name, index=index, ext="htm")
    )

    driver.save_screenshot(str(png_path))

    with open(str(htm_path), "w") as f:
        f.write(driver.page_source)

    logging.info("page dump: {index:02d}.".format(index=index))


def clean_dump(dump_path=DUMP_PATH, keep_days=1):
    dump_path = pathlib.Path(dump_path)
    time_threshold = datetime.timedelta(keep_days)

    for item in dump_path.iterdir():
        if not item.is_file():
            continue
        time_diff = datetime.datetime.now() - datetime.datetime.fromtimestamp(
            item.stat().st_mtime
        )
        if time_diff > time_threshold:
            logging.info(
                "remove {path} [{day:,} day(s) old].".format(
                    path=item.absolute(), day=time_diff.days
                )
            )
            item.unlink(missing_ok=True)


if __name__ == "__main__":
    import logger
    from config import load_config

    import logging

    logger.init("test")
    logging.info("Test")

    driver = create_driver()
    driver.quit()

    print("Finish.")
