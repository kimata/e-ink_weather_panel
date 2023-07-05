#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import functools
from flask import (
    g,
    request,
    current_app,
    after_this_request,
)
import socket
import gzip
import io


def gzipped(f):
    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @after_this_request
        def zipper(response):
            accept_encoding = request.headers.get("Accept-Encoding", "")

            if "gzip" not in accept_encoding.lower():
                return response

            response.direct_passthrough = False

            if (
                response.status_code < 200
                or response.status_code >= 300
                or "Content-Encoding" in response.headers
            ):
                return response
            gzip_buffer = io.BytesIO()
            gzip_file = gzip.GzipFile(mode="wb", fileobj=gzip_buffer)
            gzip_file.write(response.data)
            gzip_file.close()

            response.data = gzip_buffer.getvalue()
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Vary"] = "Accept-Encoding"
            response.headers["Content-Length"] = len(response.data)

            if g.pop("disable_cache", False):
                response.headers["Cache-Control"] = "no-store, must-revalidate"
                response.headers["Expires"] = "0"
            else:
                response.headers["Cache-Control"] = "max-age=86400"

            return response

        return f(*args, **kwargs)

    return view_func


def support_jsonp(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        callback = request.args.get("callback", False)
        if callback:
            content = callback + "(" + f().data.decode() + ")"
            return current_app.response_class(content, mimetype="text/javascript")
        else:
            return f(*args, **kwargs)

    return decorated_function


def remote_host(request):
    try:
        return socket.gethostbyaddr(request.remote_addr)[0]
    except:
        return request.remote_addr


def auth_user(request):
    return request.headers.get("X-Auth-Request-Email", "Unknown")
