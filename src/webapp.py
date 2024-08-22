#!/usr/bin/env python3
"""
電子ペーパ表示用の画像を表示する簡易的な Web サーバです．

Usage:
  webapp.py [-c CONFIG] [-s CONFIG] [-D]

Options:
  -c CONFIG    : 通常モードで使う設定ファイルを指定します．[default: config.yaml]
  -s CONFIG    : 小型ディスプレイモード使う設定ファイルを指定します．[default: config-small.yaml]
  -D           : ダミーモードで実行します．
"""

import atexit
import logging
import os
import pathlib

import my_lib.config
import my_lib.logger
import weather_display.generator
from flask import Flask
from flask_cors import CORS


def create_app(config_file_normal, config_file_small, dummy_mode=False):
    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # NOTE: オプションでダミーモードが指定された場合，環境変数もそれに揃えておく
        if dummy_mode:
            logging.warning("Set dummy mode")
            os.environ["DUMMY_MODE"] = "true"
        else:  # pragma: no cover
            pass

        weather_display.generator.init(pathlib.Path(__file__).parent / "create_image.py")

        def notify_terminate():  # pragma: no cover
            weather_display.generator.term()

        atexit.register(notify_terminate)
    else:  # pragma: no cover
        pass

    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/weather_panel"
    my_lib.webapp.config.init(my_lib.config.load(config_file_normal))

    import my_lib.webapp.base

    app = Flask("unit_cooler")

    CORS(app)

    app.config["CONFIG_FILE_NORMAL"] = config_file_normal
    app.config["CONFIG_FILE_SMALL"] = config_file_small
    app.config["DUMMY_MODE"] = dummy_mode

    app.register_blueprint(my_lib.webapp.base.blueprint_default)
    app.register_blueprint(my_lib.webapp.base.blueprint)
    app.register_blueprint(weather_display.generator.blueprint)

    # app.debug = True

    return app


if __name__ == "__main__":
    import docopt

    args = docopt.docopt(__doc__)

    config_file_normal = args["-c"]
    config_file_small = args["-s"]
    dummy_mode = args["-D"]

    my_lib.logger.init("panel.e-ink.weather", level=logging.INFO)

    app = create_app(config_file_normal, config_file_small, dummy_mode)

    # NOTE: スクリプトの自動リロード停止したい場合は use_reloader=False にする
    app.run(host="0.0.0.0", threaded=True, use_reloader=True)  # noqa: S104
