#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を表示する簡易的な Web サーバです．

Usage:
  webapp.py [-c CONFIG] [-s]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s           : 小型ディスプレイモードで実行します．
"""

from docopt import docopt

import sys
import logging
from flask import Flask
from flask_cors import CORS
import pathlib
import os
import atexit

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import webapp_base
import generator
import logger


if __name__ == "__main__":

    args = docopt(__doc__)

    config_file = args["-c"]
    is_small_mode = args["-s"]

    logger.init("panel.e-ink.weather", level=logging.INFO)

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        generator.init()

        def terminate():
            generator.term()

        atexit.register(terminate)

    app = Flask("unit_cooler")

    CORS(app)

    app.config["CONFIG_FILE"] = config_file
    app.config["IS_SMALL_MODE"] = is_small_mode

    app.register_blueprint(webapp_base.blueprint_default)
    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(generator.blueprint)

    # app.debug = True
    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
