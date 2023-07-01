#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import coloredlogs
import logging
import logging.handlers
import bz2
import pathlib
import os
import io

MAX_SIZE = 10 * 1024 * 1024
ROTATE_COUNT = 10

LOG_FORMAT = "{name} %(asctime)s %(levelname)s [%(filename)s:%(lineno)s %(funcName)s] %(message)s"


class GZipRotator:
    def namer(name):
        return name + ".bz2"

    def rotator(source, dest):
        with open(source, "rb") as fs:
            with bz2.open(dest, "wb") as fd:
                fd.writelines(fs)
        os.remove(source)


def init(name, level=logging.WARNING, dir_path=None, is_str=False):
    coloredlogs.install(fmt=LOG_FORMAT.format(name=name), level=level)

    if dir_path is not None:
        log_path = pathlib.Path(dir_path)
        log_path.mkdir(exist_ok=True, parents=True)

        log_file_path = str(log_path / "{name}.log".format(name=name))

        logging.info("Log to {log_file_path}".format(log_file_path=log_file_path))

        logger = logging.getLogger()
        log_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            encoding="utf8",
            maxBytes=MAX_SIZE,
            backupCount=ROTATE_COUNT,
        )
        log_handler.formatter = logging.Formatter(
            fmt=LOG_FORMAT.format(name=name), datefmt="%Y-%m-%d %H:%M:%S"
        )
        log_handler.namer = GZipRotator.namer
        log_handler.rotator = GZipRotator.rotator

        logger.addHandler(log_handler)

    if is_str:
        str_io = io.StringIO()
        handler = logging.StreamHandler(str_io)
        handler.formatter = logging.Formatter(
            fmt=LOG_FORMAT.format(name=name), datefmt="%Y-%m-%d %H:%M:%S"
        )
        logging.getLogger().addHandler(handler)

        return str_io


if __name__ == "__main__":
    init("test")
    logging.info("Test")
