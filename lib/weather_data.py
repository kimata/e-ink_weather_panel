#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


def get_clothing_yahoo(config):
    data = request.urlopen(config["URL"])
    content = html.fromstring(data.read().decode("UTF-8"))

    return {
        "today": parse_clothing(content, 1),
        "tommorow": parse_clothing(content, 2),
    }


if __name__ == "__main__":
    import logger
    from config import load_config

    import logging

    logger.init("test", level=logging.INFO)

    config = load_config()

    logging.info(get_weather_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))
    logging.info(get_clothing_yahoo(config["WEATHER"]["DATA"]["YAHOO"]))

    logging.info("Fnish.")
