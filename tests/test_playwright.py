#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import logging
import pathlib

from playwright.sync_api import expect

APP_URL_TMPL = "http://{host}:{port}/weather_panel/"
EVIDENCE_PATH = pathlib.Path(__file__).parent / "evidence"


def app_url(host, port):
    return APP_URL_TMPL.format(host=host, port=port)


######################################################################
def test_webapp(page, host, port):
    import PIL.Image

    page.set_viewport_size({"width": 2400, "height": 1600})

    page.on(
        "console",
        lambda message: logging.error(message)
        if message.type == "error"
        else logging.info(message),
    )

    page.goto(app_url(host, port))

    page.get_by_test_id("button").click()
    expect(page.get_by_test_id("button")).to_contain_text("生成中")
    expect(page.get_by_test_id("button")).to_be_enabled(timeout=180000)

    log_list = page.locator('//div[contains(@data-testid,"log")]/small/span')
    for i in range(log_list.count()):
        expect(log_list.nth(i)).not_to_contain_text("ERROR")
        expect(log_list.nth(i)).not_to_contain_text("Error")

    img_elem = page.get_by_test_id("image")
    img_base64 = img_elem.evaluate(
        """
        element => {
            var canvas = document.createElement('canvas');
            canvas.width = element.naturalWidth;
            canvas.height = element.naturalHeight;
            canvas.getContext('2d').drawImage(
                element, 0, 0, element.naturalWidth, element.naturalHeight
            );
            return canvas.toDataURL().substring("data:image/png;base64,".length)
        }
        """
    )
    img_path = EVIDENCE_PATH / "generated.png"
    with open(img_path, "wb") as f:
        f.write(base64.b64decode(img_base64))

    # NOTE: サイズが一定以上あること
    assert img_path.stat().st_size > (256 * 1024)

    # NOTE: 画像として正常に認識できること
    img_size = PIL.Image.open(img_path).size
    assert (img_size[0]) > 100 and (img_size[1] > 100)
