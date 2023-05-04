#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

import json
import logging
import os
import pathlib
import datetime

ERROR_NOTIFY_FOOTPRINT = (
    pathlib.Path(os.path.dirname(__file__)).parent / "data" / "error_notify"
)

ERROR_TMPL = """\
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


def error_impl(token, channel, message, title):
    client = WebClient(token=token)

    json_message = ERROR_TMPL.format(title=title, message=json.dumps(message))
    try:
        client.chat_postMessage(
            channel=channel,
            text=message,
            blocks=json.loads(json_message),
        )
    except SlackApiError as e:
        logging.warning(e.response["error"])


def error(token, channel, message, title="エラー", interval_min=10):
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

    error_impl(token, channel, message, title)
    ERROR_NOTIFY_FOOTPRINT.parent.mkdir(parents=True, exist_ok=True)
    ERROR_NOTIFY_FOOTPRINT.touch()


logging.getLogger("urllib3").setLevel(level=logging.WARNING)

if __name__ == "__main__":
    import logger
    from config import load_config

    logger.init("test", level=logging.DEBUG)
    logging.info("Test")

    config = load_config()
    error(
        config["SLACK"]["BOT_TOKEN"],
        config["SLACK"]["ERROR"]["CHANNEL"],
        "メッセージ",
        "タイトル",
        config["SLACK"]["ERROR"]["INTERVAL_MIN"],
    )
