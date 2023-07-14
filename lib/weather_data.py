#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
天気情報を取得します．

Usage:
  weather_data.py [-c CONFIG]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
"""


from urllib import request
from lxml import html
from datetime import datetime
import re


def parse_weather(content):
    return {
        "text": content.text_content().strip(),
        "icon_url": content.xpath("img/@src")[0].replace("_g.", "."),
    }


def parse_wind(content):
    direction, speed = content.text_content().split()

    return {"dir": direction, "speed": int(speed)}


def parse_table(content, index):
    day_info_by_type = {}
    ROW_LIST = ["hour", "weather", "temp", "humi", "precip", "wind"]

    table_xpath = '(//table[@class="yjw_table2"])[{index}]'.format(index=index)
    for row, label in enumerate(ROW_LIST):
        td_content_list = content.xpath(
            table_xpath + "//tr[{row}]/td".format(row=row + 1)
        )
        td_content_list.pop(0)
        match row:
            case 0:
                day_info_by_type[label] = list(
                    map(
                        lambda c: int(c.text_content().replace("時", "").strip()),
                        td_content_list,
                    )
                )
            case 1:
                day_info_by_type[label] = list(
                    map(lambda c: parse_weather(c), td_content_list)
                )
            case 2 | 3 | 4:
                day_info_by_type[label] = list(
                    map(lambda c: int(c.text_content().strip()), td_content_list)
                )
            case 5:
                day_info_by_type[label] = list(
                    map(lambda c: parse_wind(c), td_content_list)
                )
            case _:
                pass

    day_info_list = []
    for i in range(len(day_info_by_type[ROW_LIST[0]])):
        day_info = {}
        for label in ROW_LIST:
            day_info[label] = day_info_by_type[label][i]
        day_info_list.append(day_info)

    return day_info_list


def parse_clothing(content, index):
    table_xpath = (
        '(//dl[contains(@class, "indexList_item-clothing")])[{index}]'
        + "//dd/p[1]/@class"
    ).format(index=index)
    index = int(content.xpath(table_xpath)[0].split("-", 1)[1])

    return index


def get_weather_yahoo(config):
    data = request.urlopen(config["URL"])
    content = html.fromstring(data.read().decode("UTF-8"))

    return {
        "today": parse_table(content, 1),
        "tommorow": parse_table(content, 2),
    }


def get_clothing_yahoo(yahoo_config):
    data = request.urlopen(yahoo_config["URL"])
    content = html.fromstring(data.read().decode("UTF-8"))

    return {
        "today": parse_clothing(content, 1),
        "tommorow": parse_clothing(content, 2),
    }


def parse_wbgt_current(content):
    wbgt = content.xpath('//span[contains(@class, "present_num")]')

    if len(wbgt) == 0:
        return None
    else:
        return float(wbgt[0].text_content().strip())


def parse_wbgt_daily(content, wbgt_measured_today):
    wbgt_col_list = content.xpath(
        '//table[contains(@class, "forecast3day")]//td[contains(@class, "day")]'
    )

    if len(wbgt_col_list) != 35:
        logging.warning("Invalid format")
        return {"today": None, "tomorro": None}

    wbgt_col_list = wbgt_col_list[8:]
    wbgt_list = []
    # NOTE: 0, 3, ..., 21 時のデータが入るようにする．0 時はダミーで可．
    for i in range(27):
        if i % 9 == 0:
            # NOTE: 日付を取得しておく
            m = re.search(r"(\d+)日", wbgt_col_list[i].text_content())
            wbgt_list.append(int(m.group(1)))
        else:
            val = wbgt_col_list[i].text_content().strip()
            if len(val) == 0:
                wbgt_list.append(None)
            else:
                wbgt_list.append(int(val))

    if wbgt_list[0] == datetime.now().date().day:
        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[0] = None
        wbgt_list[9] = None

        # NOTE: 当日の過去データは実測値で差し替える
        for i in range(9):
            if wbgt_list[i] is None:
                wbgt_list[i] = wbgt_measured_today[i]

        return {
            "today": wbgt_list[0:9],
            "tommorow": wbgt_list[9:18],
        }
    else:
        # NOTE: 昨日のデータが本日として表示されている

        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[9] = None
        wbgt_list[18] = None
        return {
            "today": wbgt_list[9:18],
            "tommorow": wbgt_list[18:27],
        }


def fetch_page(url):
    import ssl
    import urllib.request

    # NOTE: 環境省のページはこれをしないとエラーになる
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    data = urllib.request.urlopen(url, context=ctx)

    return html.fromstring(data.read().decode("UTF-8"))


def get_wbgt_measured_today(wbgt_config):
    try:
        content = fetch_page(
            wbgt_config["DATA"]["ENV_GO"]["URL"].replace(
                "graph_ref_td.php", "day_list.php"
            )
        )
        wbgt_col_list = content.xpath(
            '//table[contains(@class, "asc_tbl_daylist")]//td[contains(@class, "asc_body")]'
        )

        wbgt_list = [None]
        for i, col in enumerate(wbgt_col_list):
            if i % 12 != 9:
                continue
            # NOTE: 0, 3, ..., 21 時のデータが入るようにする．0 時はダミーで可．
            val = col.text_content().strip()
            if val == "---":
                wbgt_list.append(None)
            else:
                wbgt_list.append(float(val))
        return wbgt_list
    except:
        return [None] * 9


def get_wbgt(wbgt_config):
    try:
        # NOTE: 当日の過去時間のデータは表示されず，
        # 別ページに実測値があるので，それを取ってくる．
        wbgt_measured_today = get_wbgt_measured_today(wbgt_config)

        content = fetch_page(wbgt_config["DATA"]["ENV_GO"]["URL"])

        return {
            "current": parse_wbgt_current(content),
            "daily": parse_wbgt_daily(content, wbgt_measured_today),
        }
    except:
        return {"current": None, "daily": {"today": None, "tomorro": None}}


if __name__ == "__main__":
    from docopt import docopt
    import logging

    import logger
    from config import load_config

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])

    # logging.info(get_weather_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))
    # logging.info(get_clothing_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))

    logging.info(get_wbgt(config["WBGT"]))

    logging.info("Fnish.")
