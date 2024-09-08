#!/usr/bin/env python3
"""
Liveness のチェックを行います

Usage:
  healthz.py [-c CONFIG] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -d                : デバッグモードで動作します．
"""

import logging
import pathlib
import sys

import my_lib.healthz

SCHEMA_CONFIG = "config.schema"


def check_liveness(target_list):
    for target in target_list:
        if not my_lib.healthz.check_liveness(target["name"], target["liveness_file"], target["interval"]):
            return False

    return True


######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-d"]

    my_lib.logger.init("panel.e-ink.weather", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file, pathlib.Path(SCHEMA_CONFIG))

    target_list = [
        {
            "name": name,
            "liveness_file": pathlib.Path(config["liveness"]["file"][name]),
            "interval": config["panel"]["update"]["interval"],
        }
        for name in ["display"]
    ]

    if check_liveness(target_list):
        logging.info("OK.")
        sys.exit(0)
    else:
        sys.exit(-1)
