#!/usr/bin/env python3

import io
import logging
import multiprocessing.pool
import queue
import subprocess
import threading
import time
import traceback
import uuid

import flask
import my_lib.flask_util

blueprint = flask.Blueprint("webapp", __name__, url_prefix="/")

thread_pool = None
panel_data_map = {}
create_image_path = None


def init(create_image_path_):
    global thread_pool  # noqa: PLW0603
    global create_image_path  # noqa: PLW0603

    thread_pool = multiprocessing.pool.ThreadPool(processes=3)
    create_image_path = create_image_path_


def term():
    global thread_pool

    thread_pool.close()


def image_reader(proc, token):
    global panel_data_map
    panel_data = panel_data_map[token]
    img_stream = io.BytesIO()

    try:
        while True:
            state = proc.poll()
            if state is not None:
                # プロセス終了後の残りデータを読み取り
                remaining = proc.stdout.read()
                if remaining:
                    img_stream.write(remaining)
                break
            try:
                buf = proc.stdout.read(8192)
                if buf:
                    img_stream.write(buf)
                else:
                    time.sleep(0.1)
            except OSError:
                # パイプが閉じられた場合
                break
        panel_data["image"] = img_stream.getvalue()
    except Exception:
        logging.exception("Failed to generate image")


def generate_image_impl(config_file, is_small_mode, is_dummy_mode, is_test_mode, token):
    global panel_data_map

    panel_data = panel_data_map[token]
    cmd = ["python3", create_image_path, "-c", config_file]
    if is_small_mode:
        cmd.append("-s")
    if is_dummy_mode:
        cmd.append("-d")
    if is_test_mode:
        cmd.append("-t")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)  # noqa: S603

        # NOTE: stdout も同時に読まないと、proc.poll の結果が None から
        # 変化してくれないので注意。
        thread = threading.Thread(target=image_reader, args=(proc, token))
        thread.start()

        while True:
            state = proc.poll()
            try:
                line = proc.stderr.readline()
            except OSError:
                # パイプが閉じられた場合
                break

            if line == b"":
                if state is not None:
                    break
                time.sleep(0.5)
                continue

            panel_data["log"].put(line)
            time.sleep(0.1)

        # プロセス終了を待機
        proc.wait()
        thread.join(timeout=120)

        # NOTE: None を積むことで、実行完了を通知
        panel_data["log"].put(None)
    except Exception:
        logging.exception("Failed to execute subprocess")
        panel_data["log"].put(None)


def clean_map():
    global panel_data_map

    remove_token = []
    for token, panel_data in panel_data_map.items():
        if (time.time() - panel_data["time"]) > 60:
            remove_token.append(token)

    for token in remove_token:
        del panel_data_map[token]


def generate_image(config_file, is_small_mode, is_dummy_mode, is_test_mode):
    global thread_pool
    global panel_data_map

    clean_map()

    token = str(uuid.uuid4())
    log_queue = queue.Queue()

    panel_data_map[token] = {
        "lock": threading.Lock(),
        "log": log_queue,
        "image": None,
        "time": time.time(),
    }
    thread_pool.apply_async(
        generate_image_impl,
        (config_file, is_small_mode, is_dummy_mode, is_test_mode, token),
    )

    return token


@blueprint.route("/weather_panel/api/image", methods=["POST"])
@my_lib.flask_util.gzipped
def api_image():
    global panel_data_map

    # NOTE: @gzipped をつけた場合、キャッシュ用のヘッダを付与しているので、
    # 無効化する。
    flask.g.disable_cache = True

    token = flask.request.form.get("token", "")

    if token not in panel_data_map:
        return f"Invalid token: {token}"

    image_data = panel_data_map[token]["image"]

    return flask.Response(image_data, mimetype="image/png")


@blueprint.route("/weather_panel/api/log", methods=["POST"])
def api_log():
    global panel_data_map

    token = flask.request.form.get("token", "")

    if token not in panel_data_map:
        return f"Invalid token: {token}"

    log_queue = panel_data_map[token]["log"]

    def generate():
        try:
            while True:
                while not log_queue.empty():
                    log = log_queue.get()
                    if log is None:
                        break
                    log = log.decode("utf-8")
                    yield log
                else:
                    time.sleep(0.2)
                    continue
                break
        except Exception:
            logging.exception("Failed to read log")

    res = flask.Response(flask.stream_with_context(generate()), mimetype="text/plain")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res


@blueprint.route("/weather_panel/api/run", methods=["GET"])
@my_lib.flask_util.support_jsonp
def api_run():
    mode = flask.request.args.get("mode", "")
    is_small_mode = mode == "small"
    is_test_mode = flask.request.args.get("test", False, type=bool)

    config_file = (
        flask.current_app.config["CONFIG_FILE_SMALL"]
        if is_small_mode
        else flask.current_app.config["CONFIG_FILE_NORMAL"]
    )
    is_dummy_mode = flask.current_app.config["DUMMY_MODE"]

    try:
        token = generate_image(config_file, is_small_mode, is_dummy_mode, is_test_mode)

        return flask.jsonify({"token": token})
    except Exception:
        return flask.jsonify({"token": "", "error": traceback.format_exc()})
