#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pathlib

APP_URL_PREFIX = "/weather_panel"

STATIC_FILE_PATH = pathlib.Path(__file__).parent.parent / "react" / "build"

CREATE_IMAGE_PATH = pathlib.Path(__file__).parent.parent / "app" / "create_image.py"
