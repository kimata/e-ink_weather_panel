#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import datetime
import subprocess
import time
import sys
import os
import logging
import pathlib

import logger
from config import load_config


CREATE_IMAGE = os.path.dirname(os.path.abspath(__file__)) + "/create_image.py"


def ssh_connect(hostname, key_filename):
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


logger.init("E-Ink Weather Panel")

if len(sys.argv) == 1:
    rasp_hostname = os.environ["RASP_HOSTNAME"]
else:
    rasp_hostname = sys.argv[1]

if "SSH_KEY" in os.environ:
    key_filename = os.environ["SSH_KEY"]
else:
    key_filename = (
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        + "/key/panel.id_rsa"
    )

logging.info("Raspberry Pi hostname: %s" % (rasp_hostname))

config = load_config()

while True:
    ssh = ssh_connect(rasp_hostname, key_filename)

    ssh_stdin = ssh.exec_command(
        "cat - > /dev/shm/display.png && sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?"
    )[0]

    proc = subprocess.Popen(["python3", CREATE_IMAGE], stdout=subprocess.PIPE)
    ssh_stdin.write(proc.communicate()[0])
    proc.wait()
    ssh_stdin.close()

    if proc.returncode != 0:
        logging.error(
            "Failed to create image. (code: {code})".format(code=proc.returncode)
        )
        sys.exit(proc.returncode)

    logging.info("Finish.")

    pathlib.Path(config["LIVENESS"]["FILE"]).touch()

    # 更新されていることが直感的に理解しやすくなるように，更新タイミングを 0 秒
    # に合わせる
    # (例えば，1分間隔更新だとして，1分40秒に更新されると，2分40秒まで更新されないので
    # 2分45秒くらいに表示を見た人は本当に1分間隔で更新されているのか心配になる)
    sleep_time = config["PANEL"]["UPDATE"]["INTERVAL"] - datetime.datetime.now().second
    logging.info("sleep {sleep_time} sec...".format(sleep_time=sleep_time))
    sys.stderr.flush()
    time.sleep(sleep_time)

    # NOTE: fbi コマンドのプロセスが残るので強制終了させる
    ssh.exec_command("sudo killall -9 fbi")
    ssh.close()
