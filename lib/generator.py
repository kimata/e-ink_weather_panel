#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
import sys
from flask import (
    Response,
    Blueprint,
    request,
    current_app,
    jsonify,
    stream_with_context,
)

from multiprocessing.pool import ThreadPool
import queue
import subprocess
import threading
import time
import pathlib
import io
import traceback
from multiprocessing import Queue

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

from webapp_config import CREATE_IMAGE_PATH
from flask_util import support_jsonp


blueprint = Blueprint("webapp", __name__, url_prefix="/")

thread_pool = None
panel_data_map = {}


def init():
    global thread_pool

    thread_pool = ThreadPool(processes=3)


def term():
    global thread_pool

    thread_pool.close()


def image_reader(proc, token):
    global panel_data_map
    panel_data = panel_data_map[token]
    img_stream = io.BytesIO()

    while True:
        state = proc.poll()
        buf = proc.stdout.read()
        if state is not None:
            break
        img_stream.write(buf)

    panel_data["image"] = img_stream.getvalue()


def generate_image_impl(config_file, is_small_mode, is_dummy_mode, token):
    global panel_data_map

    panel_data = panel_data_map[token]
    cmd = ["python3", CREATE_IMAGE_PATH, "-c", config_file]
    if is_small_mode:
        cmd.append("-s")
    if is_dummy_mode:
        cmd.append("-D")

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False
    )

    # NOTE: stdout も同時に読まないと，proc.poll の結果が None から
    # 変化してくれないので注意．
    thread = threading.Thread(target=image_reader, args=(proc, token))
    thread.start()

    while True:
        state = proc.poll()
        line = proc.stderr.readline()
        if line == b"":
            if state is not None:
                break
            else:
                time.sleep(0.5)
                continue
        panel_data["log"].put(line)
        time.sleep(0.1)

    thread.join()

    # NOTE: None を積むことで，実行完了を通知
    panel_data["log"].put(None)


def clean_map():
    global panel_data_map

    remove_token = []
    for token, panel_data in panel_data_map.items():
        if (time.time() - panel_data["time"]) > 60:
            remove_token.append(token)

    for token in remove_token:
        del panel_data_map[token]


def generate_image(config_file, is_small_mode, is_dummy_mode):
    global thread_pool
    global panel_data_map

    clean_map()

    token = str(uuid.uuid4())
    log_queue = Queue()

    panel_data_map[token] = {
        "lock": threading.Lock(),
        "log": log_queue,
        "image": None,
        "time": time.time(),
    }
    thread_pool.apply_async(
        generate_image_impl, (config_file, is_small_mode, is_dummy_mode, token)
    )

    return token


@blueprint.route("/weather_panel/api/image", methods=["POST"])
def api_image():
    global panel_data_map

    token = request.form.get("token", "")
    try:
        image_data = panel_data_map[token]["image"]
        res = Response(image_data, mimetype="image/png")
        return res
    except:
        return traceback.format_exc()


@blueprint.route("/weather_panel/api/log", methods=["POST"])
def api_log():
    global panel_data_map

    token = request.form.get("token", "")
    try:
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

            except queue.Empty:
                pass
            log_queue.close()

        res = Response(stream_with_context(generate()), mimetype="text/plain")
        res.headers.add("Access-Control-Allow-Origin", "*")
        res.headers.add("Cache-Control", "no-cache")
        res.headers.add("X-Accel-Buffering", "no")

        return res
    except:
        return traceback.format_exc()


@blueprint.route("/weather_panel/api/run", methods=["GET"])
@support_jsonp
def api_run():
    mode = request.args.get("mode", "")

    is_small_mode = mode == "small"

    config_file = (
        current_app.config["CONFIG_FILE_SMALL"]
        if is_small_mode
        else current_app.config["CONFIG_FILE_NORMAL"]
    )
    is_dummy_mode = current_app.config["DUMMY_MODE"]

    try:
        token = generate_image(config_file, is_small_mode, is_dummy_mode)

        return jsonify({"token": token})
    except:
        return jsonify({"token": "", "error": traceback.format_exc()})
