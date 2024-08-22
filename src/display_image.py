#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子ペーパ表示用の画像を表示します．

Usage:
  display_image.py [-c CONFIG] [-d HOSTNAME] [-s] [-t] [-O]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s           : 小型ディスプレイモードで実行します．
  -t           : テストモードで実行します．
  -d HOSTNAME  : 表示を行う Raspberry Pi のホスト名．
  -O           : 1回のみ表示
"""

import datetime
import logging
import os
import pathlib
import statistics
import subprocess
import sys
import time
import traceback

import paramiko
from docopt import docopt

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

import logger
from config import load_config
from panel_util import notify_error

import create_image

RETRY_COUNT = 3
RETRY_WAIT = 2
NOTIFY_THRESHOLD = 2
CREATE_IMAGE = os.path.dirname(os.path.abspath(__file__)) + "/create_image.py"

elapsed_list = []


def exec_patiently(func, args):
    for i in range(RETRY_COUNT):
        try:
            return func(*args)
        except Exception:
            if i == (RETRY_COUNT - 1):
                raise
            else:
                logging.warning(traceback.format_exc())
                time.sleep(RETRY_WAIT)


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
        timeout=2,
        auth_timeout=2,
    )

    return ssh


def ssh_kill_and_close(ssh, cmd):
    if ssh is None:
        return

    try:
        # NOTE: fbi コマンドのプロセスが残るので強制終了させる
        ssh.exec_command("sudo killall -9 {cmd}".format(cmd=cmd))
        ssh.close()
        return
    except AttributeError:
        return
    except:
        raise


def display_image(
    config,
    rasp_hostname,
    key_file_path,
    config_file,
    small_mode,
    test_mode,
    is_one_time,
    prev_ssh=None,
):
    start = time.perf_counter()

    exec_patiently(ssh_kill_and_close, (prev_ssh, "fbi"))

    ssh = exec_patiently(ssh_connect, (rasp_hostname, key_file_path))

    ssh_stdin = exec_patiently(
        ssh.exec_command,
        (
            "cat - > /dev/shm/display.png && "
            + "sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?",
        ),
    )[0]

    logging.info("Start drawing.")

    cmd = ["python3", CREATE_IMAGE, "-c", config_file]
    if small_mode:
        cmd.append("-s")
    if test_mode:
        cmd.append("-t")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ssh_stdin.write(proc.communicate()[0])
    proc.wait()

    ssh_stdin.close()
    print(proc.communicate()[1].decode("utf-8"), file=sys.stderr)

    # NOTE: -24 は create_image.py の異常時の終了コードに合わせる．
    if proc.returncode == 0:
        logging.info("Succeeded.")
        pathlib.Path(config["LIVENESS"]["FILE"]).touch()
    elif proc.returncode == create_image.ERROR_CODE_MAJOR:
        logging.warning("Something is wrong. (code: {code})".format(code=proc.returncode))
    elif proc.returncode == create_image.ERROR_CODE_MINOR:
        logging.warning("Something is wrong. (code: {code})".format(code=proc.returncode))
        pathlib.Path(config["LIVENESS"]["FILE"]).touch()
    else:
        logging.error("Failed to create image. (code: {code})".format(code=proc.returncode))
        sys.exit(proc.returncode)

    if is_one_time:
        # NOTE: 表示がされるまで待つ
        sleep_time = 5
    else:
        diff_sec = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST")).second
        if diff_sec > 30:
            diff_sec = 60 - diff_sec
        if diff_sec > 3:
            logging.warning("Update timing gap is large: {diff_sec}".format(diff_sec=diff_sec))

        # NOTE: 更新されていることが直感的に理解しやすくなるように，
        # 更新完了タイミングを各分の 0 秒に合わせる
        elapsed = time.perf_counter() - start

        if len(elapsed_list) >= 10:
            elapsed_list.pop(0)
        elapsed_list.append(elapsed)

        sleep_time = (
            config["PANEL"]["UPDATE"]["INTERVAL"]
            - statistics.median(elapsed_list)
            - datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST")).second
        )
        while sleep_time < 0:
            sleep_time += 60

        logging.info("sleep {sleep_time:.1f} sec...".format(sleep_time=sleep_time))

    time.sleep(sleep_time)

    return ssh


######################################################################
if __name__ == "__main__":
    args = docopt(__doc__)

    logger.init("panel.e-ink.weather", level=logging.INFO)

    config_file = args["-c"]
    is_one_time = args["-O"]
    small_mode = args["-s"]
    rasp_hostname = os.environ.get("RASP_HOSTNAME", args["-d"])
    test_mode = args["-t"]
    key_file_path = os.environ.get(
        "SSH_KEY",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/key/panel.id_rsa",
    )

    logging.info("Raspberry Pi hostname: %s" % (rasp_hostname))

    config = load_config(config_file)

    fail_count = 0
    prev_ssh = None
    while True:
        try:
            prev_ssh = display_image(
                config,
                rasp_hostname,
                key_file_path,
                config_file,
                small_mode,
                test_mode,
                is_one_time,
                prev_ssh,
            )
            fail_count = 0

            if is_one_time:
                break
        except:
            fail_count += 1
            if is_one_time or (fail_count >= NOTIFY_THRESHOLD):
                notify_error(config, traceback.format_exc())
                logging.error("エラーが続いたので終了します．")
                sys.stderr.flush()
                time.sleep(1)
                raise
            else:
                time.sleep(10)
                pass
