#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import datetime
import subprocess
import time
import sys
import os
import gc

UPDATE_SEC = 60
FAIL_MAX = 5

CREATE_IMAGE = os.path.dirname(os.path.abspath(__file__)) + "/create_image.py"


def ssh_connect(hostname, key_filename):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname,
        username="ubuntu",
        key_filename=key_filename,
        allow_agent=True,
        look_for_keys=False,
    )
    return ssh


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

print("Raspberry Pi hostname: %s" % (rasp_hostname))

ssh = ssh_connect(rasp_hostname, key_filename)

fail = 0
while True:
    ssh_stdin = None
    try:
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(
            "cat - > /dev/shm/display.png && sudo fbi -1 -T 1 -d /dev/fb0 --noverbose /dev/shm/display.png; echo $?"
        )

        proc = subprocess.Popen(["python3", CREATE_IMAGE], stdout=subprocess.PIPE)
        ssh_stdin.write(proc.communicate()[0])
        ssh_stdin.close()

        ret_code = int(ssh_stdout.read().decode("utf-8").strip())
        if ret_code != 0:
            raise RuntimeError(ssh_stderr.read().decode("utf-8"))

        fail = 0
        print(".", end="")
        sys.stdout.flush()
    except:
        import traceback

        print("")
        print(traceback.format_exc(), file=sys.stderr)
        sys.stdout.flush()
        fail += 1
        time.sleep(10)
        ssh = ssh_connect(rasp_hostname, key_filename)

    # close だけだと，SSH 側がしばらく待っていることがあったので，念のため
    del ssh_stdin
    gc.collect()

    if fail > FAIL_MAX:
        sys.stderr.write("接続エラーが続いたので終了します．\n")
        sys.exit(-1)

    # 更新されていることが直感的に理解しやすくなるように，更新タイミングを 0 秒
    # に合わせる
    # (例えば，1分間隔更新だとして，1分40秒に更新されると，2分40秒まで更新されないので
    # 2分45秒くらいに表示を見た人は本当に1分間隔で更新されているのか心配になる)
    time.sleep(UPDATE_SEC - datetime.datetime.now().second)
