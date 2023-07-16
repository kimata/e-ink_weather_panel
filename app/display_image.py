#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を表示します．

Usage:
  display_image.py [-c CONFIG] [-t HOSTNAME] [-s] [-O]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s           : 小型ディスプレイモードで実行します．
  -t HOSTNAME  : 表示を行う Raspberry Pi のホスト名．
  -O           : 1回のみ表示
"""

from docopt import docopt

import paramiko
import datetime
import subprocess
import time
import sys
import os
import logging
import pathlib
import traceback
import statistics

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import logger
from config import load_config
import notify_slack

NOTIFY_THRESHOLD = 2
CREATE_IMAGE = os.path.dirname(os.path.abspath(__file__)) + "/create_image.py"

elapsed_list = []


def notify_error(config, message):
    if "SLACK" not in config:
        return

    notify_slack.error(
        config["SLACK"]["BOT_TOKEN"],
        config["SLACK"]["ERROR"]["CHANNEL"]["NAME"],
        "E-Ink Weather Panel",
        message,
        config["SLACK"]["ERROR"]["INTERVAL_MIN"],
    )


def ssh_connect(hostname, key_filename):
    logging.info("Connect to {hostname}".format(hostname=hostname))

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname,
        username="ubuntu",
        pkey=paramiko.RSAKey.from_private_key(open(key_filename)),
        allow_agent=False,
        look_for_keys=False,
    )
    return ssh


def display_image(config, args, old_ssh, is_small_mode, is_one_time):
    start = time.perf_counter()

    if old_ssh is not None:
        # NOTE: fbi コマンドのプロセスが残るので強制終了させる
        old_ssh.exec_command("sudo killall -9 fbi")
        old_ssh.close()

    ssh = ssh_connect(rasp_hostname, key_file_path)

    ssh_stdin = ssh.exec_command(
        "cat - > /dev/shm/display.png && sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?"
    )[0]

    logging.info("Start drawing.")
    cmd = ["python3", CREATE_IMAGE, "-c", args["-c"]]
    if is_small_mode:
        cmd.append("-s")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ssh_stdin.write(proc.communicate()[0])
    proc.wait()
    ssh_stdin.close()
    print(proc.communicate()[1].decode("utf-8"), file=sys.stderr)

    # NOTE: -24 は create_image.py の異常時の終了コードに合わせる．
    if proc.returncode == 0:
        logging.info("Success.")
    elif proc.returncode == 222:
        logging.warning("Finish. (something is wrong)")
    else:
        logging.error(
            "Failed to create image. (code: {code})".format(code=proc.returncode)
        )
        sys.exit(proc.returncode)

    pathlib.Path(config["LIVENESS"]["FILE"]).touch()

    if is_one_time:
        # NOTE: 表示がされるまで待つ
        sleep_time = 5
    else:
        diff_sec = datetime.datetime.now().second
        if diff_sec > 30:
            diff_sec = 60 - diff_sec
        if diff_sec > 3:
            logging.warning(
                "Update timing gap is large: {diff_sec}".format(diff_sec=diff_sec)
            )

        # NOTE: 更新されていることが直感的に理解しやすくなるように，
        # 更新完了タイミングを各分の 0 秒に合わせる
        elapsed = time.perf_counter() - start

        if len(elapsed_list) >= 10:
            elapsed_list.pop(0)
        elapsed_list.append(elapsed)

        sleep_time = (
            config["PANEL"]["UPDATE"]["INTERVAL"]
            - statistics.median(elapsed_list)
            - datetime.datetime.now().second
        )
        if sleep_time < 0:
            sleep_time += 60

        logging.info("sleep {sleep_time} sec...".format(sleep_time=sleep_time))

    time.sleep(sleep_time)

    return ssh


######################################################################
args = docopt(__doc__)

logger.init("panel.e-ink.weather", level=logging.INFO)

is_one_time = args["-O"]
is_small_mode = args["-s"]
rasp_hostname = os.environ.get("RASP_HOSTNAME", args["-t"])
key_file_path = os.environ.get(
    "SSH_KEY",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/key/panel.id_rsa",
)

logging.info("Raspberry Pi hostname: %s" % (rasp_hostname))

config = load_config(args["-c"])

fail_count = 0
ssh = None
while True:
    try:
        ssh = display_image(config, args, ssh, is_small_mode, is_one_time)
        fail_count = 0

        if is_one_time:
            break
    except:
        fail_count += 1
        if is_one_time or (fail_count >= NOTIFY_THRESHOLD):
            notify_error(config, traceback.format_exc())
            logging.error("エラーが続いたので終了します．")
            raise
        else:
            time.sleep(10)
            pass
