#!/usr/bin/env python3
"""
電子ペーパ表示用の画像を表示します．

Usage:
  display_image.py [-c CONFIG] [-d HOSTNAME] [-s] [-t] [-O]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -s                : 小型ディスプレイモードで実行します．
  -t                : テストモードで実行します．
  -d HOSTNAME       : 表示を行う Raspberry Pi のホスト名．
  -O                : 1回のみ表示
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

import create_image
import my_lib.footprint
import my_lib.panel_util
import paramiko
from docopt import docopt

SCHEMA_CONFIG = "config.schema"
SCHEMA_CONFIG_SMALL = "config-small.schema"

RETRY_COUNT = 3
RETRY_WAIT = 2
NOTIFY_THRESHOLD = 2
CREATE_IMAGE = pathlib.Path(__file__).parent / "create_image.py"

elapsed_list = []


def exec_patiently(func, args):
    for i in range(RETRY_COUNT):  # noqa: RET503
        try:
            return func(*args)
        except Exception:  # noqa: PERF203
            if i == (RETRY_COUNT - 1):
                raise
            logging.warning(traceback.format_exc())
            time.sleep(RETRY_WAIT)


def ssh_connect(hostname, key_filename):
    logging.info("Connect to %s", hostname)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # noqa: S507

    with open(key_filename) as f:  # noqa: PTH123
        ssh.connect(
            hostname,
            username="ubuntu",
            pkey=paramiko.RSAKey.from_private_key(f),
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
        ssh.exec_command(f"sudo killall -9 {cmd}")
        ssh.close()
        return
    except AttributeError:
        return
    except:
        raise


def exec_display_image(ssh, config_file, small_mode, test_mode):
    ssh_stdin, ssh_stdout, ssh_stderr = exec_patiently(
        ssh.exec_command,
        (
            "cat - > /dev/shm/display.png && "
            "sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?",
        ),
    )

    logging.info("Start drawing.")

    cmd = ["python3", CREATE_IMAGE, "-c", config_file]
    if small_mode:
        cmd.append("-s")
    if test_mode:
        cmd.append("-t")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # noqa: S603
    ssh_stdin.write(proc.communicate()[0])
    proc.wait()

    ssh_stdin.flush()
    ssh_stdin.channel.shutdown_write()

    logging.info(proc.communicate()[1].decode("utf-8"))

    fbi_status = ssh_stdout.channel.recv_exit_status()

    # NOTE: -24 は create_image.py の異常時の終了コードに合わせる．
    if (fbi_status == 0) and (proc.returncode == 0):
        logging.info("Succeeded.")
        my_lib.footprint.update(pathlib.Path(config["liveness"]["file"]["display"]))
    elif proc.returncode == create_image.ERROR_CODE_MAJOR:
        logging.warning("Failed to create image at all. (code: %d)", proc.returncode)
    elif proc.returncode == create_image.ERROR_CODE_MINOR:
        logging.warning("Failed to create image partially. (code: %d)", proc.returncode)
        my_lib.footprint.update(pathlib.Path(config["liveness"]["file"]["display"]))
    elif fbi_status != 0:
        logging.warning("Failed to display image. (code: %d)", fbi_status)
        logging.warning("[stdout] %s", ssh_stdout.read().decode("utf-8"))
        logging.warning("[stderr] %s", ssh_stderr.read().decode("utf-8"))
    else:
        logging.error("Failed to create image. (code: %d)", proc.returncode)
        sys.exit(proc.returncode)

    ssh_stdin.close()
    ssh_stdout.close()
    ssh_stderr.close()


def display_image(  # noqa: PLR0913
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

    exec_display_image(ssh, config_file, small_mode, test_mode)

    if is_one_time:
        # NOTE: 表示がされるまで待つ
        sleep_time = 5
    else:
        diff_sec = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST")).second
        if diff_sec > 30:
            diff_sec = 60 - diff_sec
        if diff_sec > 3:
            logging.warning("Update timing gap is large: %d", diff_sec)

        # NOTE: 更新されていることが直感的に理解しやすくなるように，
        # 更新完了タイミングを各分の 0 秒に合わせる
        elapsed = time.perf_counter() - start

        if len(elapsed_list) >= 10:
            elapsed_list.pop(0)
        elapsed_list.append(elapsed)

        sleep_time = (
            config["panel"]["update"]["interval"]
            - statistics.median(elapsed_list)
            - datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST")).second
        )
        while sleep_time < 0:
            sleep_time += 60

        logging.info("sleep %.1f sec...", sleep_time)

    time.sleep(sleep_time)

    return ssh


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    is_one_time = args["-O"]
    small_mode = args["-s"]
    rasp_hostname = os.environ.get("RASP_HOSTNAME", args["-d"])
    test_mode = args["-t"]
    key_file_path = os.environ.get(
        "SSH_KEY",
        pathlib.Path("key/panel.id_rsa"),
    )

    my_lib.logger.init("panel.e-ink.weather", level=logging.INFO)

    config = my_lib.config.load(
        config_file, pathlib.Path(SCHEMA_CONFIG_SMALL if small_mode else SCHEMA_CONFIG)
    )

    logging.info("Raspberry Pi hostname: %s", rasp_hostname)

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
        except Exception:
            logging.exception("Failed to display image")
            fail_count += 1
            if is_one_time or (fail_count >= NOTIFY_THRESHOLD):
                my_lib.panel_util.notify_error(config, traceback.format_exc())
                logging.error("エラーが続いたので終了します．")  # noqa: TRY400
                sys.stderr.flush()
                time.sleep(1)
                raise
            else:
                time.sleep(10)
