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


def parse_wbgt(content):
    wbgt = content.xpath('//span[contains(@class, "present_num")]')

    if len(wbgt) == 0:
        return None
    else:
        return float(wbgt[0].text_content().strip())


def get_wbgt(wbgt_config):
    import ssl
    import urllib.request

    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    # Use urllib to open the URL and read the content
    data = urllib.request.urlopen(wbgt_config["URL"], context=ctx)

    # data = request.urlopen(wbgt_config["URL"])
    content = html.fromstring(data.read().decode("UTF-8"))

    return parse_wbgt(content)


if __name__ == "__main__":
    from docopt import docopt
    import logging

    import logger
    from config import load_config

    args = docopt(__doc__)

    logger.init("test", level=logging.INFO)

    config = load_config(args["-c"])

    logging.info(get_weather_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))
    logging.info(get_clothing_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))

    logging.info(get_wbgt(config["WEATHER"]["DATA"]["ENV_WBGT"]))

    logging.info("Fnish.")
