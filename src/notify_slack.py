#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import slack_sdk

import json
import logging
import os
import pathlib
import datetime

ERROR_NOTIFY_FOOTPRINT = (
    pathlib.Path(os.path.dirname(__file__)).parent / "data" / "error_notify"
)

SIMPLE_TMPL = """\
[
    {{
        "type": "header",
	"text": {{
            "type": "plain_text",
	    "text": "{title}",
            "emoji": true
        }}
    }},
    {{
        "type": "section",
        "text": {{
            "type": "mrkdwn",
	    "text": {message}
	}}
    }}
]
"""


def format_simple(title, message):
    return {
        "text": message,
        "json": json.loads(
            SIMPLE_TMPL.format(title=title, message=json.dumps(message))
        ),
    }


def send(token, channel, message):
    client = slack_sdk.WebClient(token=token)

    try:
        client.chat_postMessage(
            channel=channel,
            text=message["text"],
            blocks=message["json"],
        )
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])


def split_send(token, channel, title, message, formatter=format_simple):
    LINE_SPLIT = 20

    message_lines = message.splitlines()
    for i in range(0, len(message_lines), LINE_SPLIT):
        send(
            token,
            channel,
            formatter(title, "\n".join(message_lines[i : i + LINE_SPLIT])),
        )


def info(token, channel, message, formatter=format_simple):
    title = "Info"
    split_send(token, channel, title, message, formatter)


def error(token, channel, message, interval_min=10, formatter=format_simple):
    title = "Error"

    if (
        ERROR_NOTIFY_FOOTPRINT.exists()
        and (
            datetime.datetime.now()
            - datetime.datetime.fromtimestamp(ERROR_NOTIFY_FOOTPRINT.stat().st_mtime)
        ).seconds
        < interval_min * 60
    ):
        logging.info("skip slack nofity")
        return

    split_send(token, channel, title, message, formatter)

    ERROR_NOTIFY_FOOTPRINT.parent.mkdir(parents=True, exist_ok=True)
    ERROR_NOTIFY_FOOTPRINT.touch()


if __name__ == "__main__":
    import logger
    import sys
    from config import load_config

    logger.init("test", level=logging.WARNING)
    logging.info("Test")

    config = load_config()
    if "SLACK" not in config:
        logging.warning("Slack の設定が記載されていません．")
        sys.exit(-1)

    if "INFO" in config["SLACK"]:
        info(
            config["SLACK"]["BOT_TOKEN"],
            config["SLACK"]["INFO"]["CHANNEL"],
            "メッセージ\nメッセージ",
        )

    if "ERROR" in config["SLACK"]:
        error(
            config["SLACK"]["BOT_TOKEN"],
            config["SLACK"]["ERROR"]["CHANNEL"],
            "エラーメッセージ",
            config["SLACK"]["ERROR"]["INTERVAL_MIN"],
        )
