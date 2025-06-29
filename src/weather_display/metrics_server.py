#!/usr/bin/env python3
"""
メトリクスを WebUI で提供します。

Usage:
  metrics_server.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import logging
import threading

import flask
import flask_cors
import werkzeug.serving


def create_app(config, event_queue):
    import my_lib.webapp.config

    my_lib.webapp.config.URL_PREFIX = "/weather_panel"
    my_lib.webapp.config.init()
    # my_lib.config.load(config_file_normal, pathlib.Path(SCHEMA_CONFIG))
    # my_lib.webapp.config.init(config["actuator"]["log_server"])

    import my_lib.webapp.base
    import my_lib.webapp.event
    import my_lib.webapp.log
    import my_lib.webapp.util

    import unit_cooler.actuator.api.flow_status
    import unit_cooler.actuator.api.metrics
    import unit_cooler.actuator.api.valve_status

    # NOTE: アクセスログは無効にする
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    app = flask.Flask("unit-cooler-log")

    flask_cors.CORS(app)

    app.config["CONFIG"] = config

    app.json.compat = True

    app.register_blueprint(my_lib.webapp.log.blueprint)
    app.register_blueprint(my_lib.webapp.event.blueprint)
    app.register_blueprint(my_lib.webapp.util.blueprint)
    app.register_blueprint(unit_cooler.actuator.api.valve_status.blueprint)
    app.register_blueprint(unit_cooler.actuator.api.flow_status.blueprint)
    app.register_blueprint(unit_cooler.actuator.api.metrics.blueprint)

    my_lib.webapp.config.show_handler_list(app)

    my_lib.webapp.log.init(config)
    my_lib.webapp.event.start(event_queue)

    # メトリクスデータベースの初期化
    with app.app_context():
        import unit_cooler.actuator.api.metrics

        unit_cooler.actuator.api.metrics.init_metrics_db()

    # app.debug = True

    return app


def start(config, event_queue, port):
    # NOTE: Flask は別のプロセスで実行
    server = werkzeug.serving.make_server(
        "0.0.0.0",  # noqa: S104
        port,
        create_app(config, event_queue),
        threaded=True,
    )
    thread = threading.Thread(target=server.serve_forever)

    logging.info("Start log server")

    thread.start()

    return {
        "server": server,
        "thread": thread,
    }


def term(handle):
    import my_lib.webapp.event

    logging.warning("Stop log server")

    my_lib.webapp.event.term()

    handle["server"].shutdown()
    handle["server"].server_close()
    handle["thread"].join()

    my_lib.webapp.log.term()


if __name__ == "__main__":
    # TEST Code
    import multiprocessing

    import docopt
    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    event_queue = multiprocessing.Queue()

    log_server_handle = start(config, event_queue)
