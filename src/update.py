#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
import os
import pathlib
import pprint
import PIL.Image
import io
import wsgiref.handlers
import time
from requests import Request, Session
import hmac
import hashlib
import base64

from weather_panel import create_weather_panel
from power_graph import create_power_graph
from sensor_graph import create_sensor_graph

CONFIG_PATH = "../config.yml"


def load_config():
    path = str(pathlib.Path(os.path.dirname(__file__), CONFIG_PATH))
    with open(path, "r") as file:
        return yaml.load(file, Loader=yaml.SafeLoader)


def upload(img_stream, server_ip, uuid, api_secret, api_key):
    method = "PUT"
    api = "/backend/{uuid}".format(uuid=uuid)

    headers = {
        "Date": wsgiref.handlers.format_date_time(time.time()),
    }

    req = Request(
        method,
        "http://{server_ip}:8081{api}".format(server_ip=server_ip, api=api),
        files=[("image", ("weather.png", img_stream, "image/png"))],
        headers=headers,
    )

    prepped = req.prepare()

    h = hmac.new(
        api_secret.encode("utf-8"),
        "{method}\n\n{content_type}\n{date}\n{api}".format(
            method=method,
            content_type=prepped.headers["Content-Type"],
            date=headers["Date"],
            api=api,
        ).encode("utf-8"),
        hashlib.sha256,
    )

    prepped.headers["Authorization"] = (
        api_key + ":" + (base64.encodebytes(h.digest()).strip()).decode("utf-8")
    )

    return Session().send(prepped)


config = load_config()

weather_panel_img = create_weather_panel(config["WEATHER"], config["FONT"])
power_graph_img = create_power_graph(
    config["INFLUXDB"], config["POWER"], config["FONT"]
)
sensor_graph_img = create_sensor_graph(
    config["INFLUXDB"], config["SENSOR"], config["FONT"]
)

img = PIL.Image.new(
    "RGBA",
    (config["PANEL"]["DEVICE"]["WIDTH"], config["PANEL"]["DEVICE"]["HEIGHT"]),
    (255, 255, 255, 255),
)
img.paste(
    power_graph_img, (0, config["WEATHER"]["HEIGHT"] - config["POWER"]["OVERLAP"])
)
weather_panel_img.save("weather_panel.png", "PNG")
img.alpha_composite(weather_panel_img, (0, 0))
img.paste(
    sensor_graph_img,
    (
        0,
        config["WEATHER"]["HEIGHT"]
        + config["POWER"]["HEIGHT"]
        - config["POWER"]["OVERLAP"]
        - config["SENSOR"]["OVERLAP"],
    ),
)

bytes_io = io.BytesIO()
img.save(bytes_io, "PNG")
bytes_io.seek(0)

img.save("result.png", "PNG")

r = upload(
    bytes_io,
    config["PANEL"]["SERVER"]["IP"],
    config["PANEL"]["DEVICE"]["UUID"],
    config["PANEL"]["SERVER"]["API_SECRET"],
    config["PANEL"]["SERVER"]["API_KEY"],
)

if r.status_code == 200:
    print("OK")
else:
    print("ERROR")
