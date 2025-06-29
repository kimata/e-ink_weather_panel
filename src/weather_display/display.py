import logging
import pathlib
import subprocess
import sys
import time
import traceback

import my_lib.footprint
import my_lib.panel_util
import my_lib.proc_util
import paramiko

import create_image

RETRY_COUNT = 3
RETRY_WAIT = 2
CREATE_IMAGE = pathlib.Path(__file__).parent.parent / "create_image.py"


def exec_patiently(func, args):
    for i in range(RETRY_COUNT):
        try:
            return func(*args)
        except Exception:  # noqa: PERF203
            if i == (RETRY_COUNT - 1):
                raise
            logging.warning(traceback.format_exc())
            time.sleep(RETRY_WAIT)
    return None


def ssh_connect_impl(hostname, key_filename):
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


def ssh_kill_and_close_impl(ssh, cmd):
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


def ssh_kill_and_close(ssh, cmd):
    exec_patiently(ssh_kill_and_close_impl, (ssh, cmd))


def ssh_connect(hostname, key_file_path):
    return exec_patiently(ssh_connect_impl, (hostname, key_file_path))


def execute(ssh, config, config_file, small_mode, test_mode):
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

    # NOTE: -24 は create_image.py の異常時の終了コードに合わせる。
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

    my_lib.proc_util.reap_zombie()
