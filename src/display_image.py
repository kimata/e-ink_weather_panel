#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を表示します．

Usage:
  display_image.py [-f CONFIG] [-t HOSTNAME] [-s] [-O]

Options:
  -f CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
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

import logger
from config import load_config
import notify_slack

NOTIFY_THRESHOLD = 2
CREATE_IMAGE = os.path.dirname(os.path.abspath(__file__)) + "/create_image.py"


def notify_error(config):
    notify_slack.error(
        config["SLACK"]["BOT_TOKEN"],
        config["SLACK"]["ERROR"]["CHANNEL"],
        "E-Ink Weather Panel",
        traceback.format_exc(),
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


def display_image(config, args, is_small_mode, is_onece):
    ssh = ssh_connect(rasp_hostname, key_file_path)

    ssh_stdin = ssh.exec_command(
        "cat - > /dev/shm/display.png && sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?"
    )[0]

    logging.info("Start drawing.")
    cmd = ["python3", CREATE_IMAGE, "-f", args["-f"]]
    if is_small_mode:
        cmd.append("-s")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    ssh_stdin.write(proc.communicate()[0])
    proc.wait()
    ssh_stdin.close()

    # NOTE: -24 は create_image.py の異常時の終了コードに合わせる．
    if proc.returncode == 0:
        logging.info("Success.")
    elif proc.returncode != 222:
        logging.warn("Finish. (something is wrong)")
    else:
        logging.error(
            "Failed to create image. (code: {code})".format(code=proc.returncode)
        )
        sys.exit(proc.returncode)

    pathlib.Path(config["LIVENESS"]["FILE"]).touch()

    if is_onece:
        # NOTE: 表示がされるまで待つ
        sleep_time = 5
    else:
        # NOTE: 更新されていることが直感的に理解しやすくなるように，
        # 更新タイミングを 0 秒に合わせる
        # (例えば，1分間隔更新だとして，1分40秒に更新されると，2分40秒まで更新されないので
        # 2分45秒くらいに表示を見た人は本当に1分間隔で更新されているのか心配になる)
        sleep_time = (
            config["PANEL"]["UPDATE"]["INTERVAL"] - datetime.datetime.now().second
        )
        logging.info("sleep {sleep_time} sec...".format(sleep_time=sleep_time))

    sys.stderr.flush()
    time.sleep(sleep_time)

    # NOTE: fbi コマンドのプロセスが残るので強制終了させる
    ssh.exec_command("sudo killall -9 fbi")
    ssh.close()


######################################################################
args = docopt(__doc__)

logger.init("panel.e-ink.weather", level=logging.INFO)

is_onece = args["-O"]
is_small_mode = args["-s"]
rasp_hostname = os.environ.get("RASP_HOSTNAME", args["-t"])
key_file_path = os.environ.get(
    "SSH_KEY",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/key/panel.id_rsa",
)

logging.info("Raspberry Pi hostname: %s" % (rasp_hostname))

config = load_config(args["-f"])

fail_count = 0
while True:
    try:
        display_image(config, args, is_small_mode, is_onece)
        fail_count = 0

        if is_onece:
            break
    except:
        fail_count += 1
        if is_onece or (fail_count >= NOTIFY_THRESHOLD):
            if "SLACK" in config:
                notify_error(config)
            logging.error("エラーが続いたので終了します．")
            raise
        else:
            time.sleep(10)
            pass
