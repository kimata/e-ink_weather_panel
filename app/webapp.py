#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を表示する簡易的な Web サーバです．

Usage:
  webapp.py [-c CONFIG] [-s] [-D]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s           : 小型ディスプレイモードで実行します．
  -D           : ダミーモードで実行します．
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
    small_mode = args["-s"]
    dummy_mode = args["-D"]

    logger.init("panel.e-ink.weather", level=logging.INFO)

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
        if dummy_mode:
            logging.warning("Set dummy mode")
            os.environ["DUMMY_MODE"] = "true"

        generator.init()

        def terminate():
            generator.term()

        atexit.register(terminate)

    app = Flask("unit_cooler")

    CORS(app)

    app.config["CONFIG_FILE"] = config_file
    app.config["SMALL_MODE"] = small_mode
    app.config["DUMMY_MODE"] = dummy_mode

    app.register_blueprint(webapp_base.blueprint_default)
    app.register_blueprint(webapp_base.blueprint)
    app.register_blueprint(generator.blueprint)

    # app.debug = True
    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)
