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


def send(token, channel, title, message):
    client = slack_sdk.WebClient(token=token)

    try:
        client.chat_postMessage(
            channel=channel,
            text=message["text"],
            blocks=message["json"],
        )
    except slack_sdk.errors.SlackApiError as e:
        logging.warning(e.response["error"])


def info(
    token, channel, message, title="Info", interval_min=10, formatter=format_simple
):
    send(
        token,
        channel,
        title,
        formatter(title, message),
    )


def error(
    token, channel, message, title="エラー", interval_min=10, formatter=format_simple
):
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

    send(
        token,
        channel,
        title,
        formatter(title, message),
    )

    ERROR_NOTIFY_FOOTPRINT.parent.mkdir(parents=True, exist_ok=True)
    ERROR_NOTIFY_FOOTPRINT.touch()


# NOTE: Slack SDK のロギングレベルは常に WARNING に固定する
logging.getLogger(slack_sdk.web.base_client.__name__).setLevel(logging.WARNING)


if __name__ == "__main__":
    import logger
    import sys
    from config import load_config

    logger.init("test", level=logging.DEBUG)
    logging.info("Test")

    config = load_config()
    if "SLACK" not in config:
        logging.warning("Slack の設定が記載されていません．")
        sys.exit(-1)

    if "INFO" in config["SLACK"]:
        info(
            config["SLACK"]["BOT_TOKEN"],
            config["SLACK"]["INFO"]["CHANNEL"],
            "メッセージ",
        )

    if "ERROR" in config["SLACK"]:
        error(
            config["SLACK"]["BOT_TOKEN"],
            config["SLACK"]["ERROR"]["CHANNEL"],
            "エラーメッセージ",
            "テスト",
            config["SLACK"]["ERROR"]["INTERVAL_MIN"],
        )
