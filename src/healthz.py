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
from docopt import docopt

sys.path.append(str(pathlib.Path(__file__).parent.parent / "lib"))

######################################################################
if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]

    my_lib.logger.init("panel.e-ink.weather", level=logging.INFO)

    logging.info("Using config config: %s", config_file)
    config = my_lib.config.load(config_file)

    # liveness_file = pathlib.Path(config["LIVENESS"]["FILE"])

    # if not liveness_file.exists():
    #     logging.warning("Not executed.")
    #     sys.exit(-1)

    # elapsed = datetime.datetime.now() - datetime.datetime.fromtimestamp(liveness_file.stat().st_mtime)
    # if elapsed.total_seconds() > config["PANEL"]["UPDATE"]["INTERVAL"]:
    #     logging.warning("Execution interval is too long. ({elapsed:,} sec)".format(elapsed=elapsed.seconds))
    #     sys.exit(-1)

    # logging.info("OK.")
    # sys.exit(0)
