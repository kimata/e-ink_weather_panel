#!/usr/bin/env python3

import concurrent.futures
import io
import logging
import queue
import subprocess
import threading
import time
import traceback
import uuid

import flask
import my_lib.flask_util
import my_lib.webapp.config

blueprint = flask.Blueprint("webapp", __name__, url_prefix=my_lib.webapp.config.URL_PREFIX)

thread_pool = None
panel_data_map = {}
create_image_path = None


def init(create_image_path_):
    global thread_pool  # noqa: PLW0603
    global create_image_path  # noqa: PLW0603

    # ThreadPoolExecutorに変更してより効率的な非同期処理を実現
    thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=3, thread_name_prefix="image_gen")
    create_image_path = create_image_path_


def term():
    global thread_pool

    if thread_pool:
        thread_pool.shutdown(wait=True)


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


def log_reader(proc, token):
    global panel_data_map

    panel_data = panel_data_map[token]

    try:
        while True:
            line = proc.stderr.readline()
            if not line:
                break
            panel_data["log"].put(line)
    except Exception:
        logging.exception("Failed to read log")


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

        # 非同期でstdoutとstderrを読み取り
        stdout_thread = threading.Thread(target=image_reader, args=(proc, token))
        stderr_thread = threading.Thread(target=log_reader, args=(proc, token))

        stdout_thread.start()
        stderr_thread.start()

        # プロセス終了を非ブロッキングで監視
        while proc.poll() is None:
            time.sleep(0.1)

        # プロセス終了を待機（タイムアウト付き）
        try:
            proc.wait(timeout=120)
        except subprocess.TimeoutExpired:
            logging.warning("Subprocess timed out, terminating")
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

        # スレッドの終了を待機（タイムアウト付き）
        stdout_thread.join(timeout=30)
        stderr_thread.join(timeout=30)

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
        "future": None,
    }

    # ThreadPoolExecutorのsubmitを使用して非同期実行
    future = thread_pool.submit(
        generate_image_impl, config_file, is_small_mode, is_dummy_mode, is_test_mode, token
    )
    panel_data_map[token]["future"] = future

    return token


@blueprint.route("/api/image", methods=["POST"])
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


@blueprint.route("/api/log", methods=["POST"])
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
                    time.sleep(0.1)
                    continue
                break
        except Exception:
            logging.exception("Failed to read log")

    res = flask.Response(flask.stream_with_context(generate()), mimetype="text/plain")
    res.headers.add("Access-Control-Allow-Origin", "*")
    res.headers.add("Cache-Control", "no-cache")
    res.headers.add("X-Accel-Buffering", "no")

    return res


@blueprint.route("/api/run", methods=["GET"])
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
