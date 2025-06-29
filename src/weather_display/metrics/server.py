#!/usr/bin/env python3
"""
メトリクスを WebUI で提供します。

Usage:
  metrics_server.py [-c CONFIG] [-p PORT] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -p PORT           : Web サーバーを動作させるポートを指定します。[default: 5000]
  -D                : デバッグモードで動作します。
"""

import logging
import threading

import flask
import flask_cors
import werkzeug.serving


def create_app(config):
    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/weather_panel"

    import weather_display.metrics.webapi.page

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = flask.Flask("unit_cooler")

    flask_cors.CORS(app)

    app.config["CONFIG"] = config

    app.json.compat = True

    app.register_blueprint(weather_display.metrics.webapi.page.blueprint)

    my_lib.webapp.config.show_handler_list(app)

    # app.debug = True

    return app


def start(config, port):
    # NOTE: Flask は別のプロセスで実行
    server = werkzeug.serving.make_server(
        "0.0.0.0",  # noqa: S104
        port,
        create_app(config),
        threaded=True,
    )
    thread = threading.Thread(target=server.serve_forever)

    logging.info("Start metrics server")

    thread.start()

    return {
        "server": server,
        "thread": thread,
    }


def term(handle):
    logging.warning("Stop metrics server")

    handle["server"].shutdown()
    handle["server"].server_close()
    handle["thread"].join()


if __name__ == "__main__":
    # TEST Code

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    port = int(args["-p"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    metrics_server_handle = start(config, port)

    try:
        # サーバーを継続実行
        metrics_server_handle["thread"].join()
    except KeyboardInterrupt:
        logging.info("Stopping metrics server...")
        term(metrics_server_handle)
