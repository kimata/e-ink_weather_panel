#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import datetime
import subprocess
import time
import sys
import os
import gc

UPDATE_SEC = 120

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
        + "/key/panel.id_dsa"
    )

print("Raspberry Pi hostname: %s" % (rasp_hostname))

ssh = ssh_connect(rasp_hostname, key_filename)

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

        print(".", end="")
        sys.stdout.flush()
    except:
        import traceback

        print("")
        print(traceback.format_exc(), file=sys.stderr)
        sys.stdout.flush()

        break

    # close だけだと，SSH 側がしばらく待っていることがあったので，念のため
    del ssh_stdin
    gc.collect()

    time.sleep(UPDATE_SEC - datetime.datetime.now().second)
