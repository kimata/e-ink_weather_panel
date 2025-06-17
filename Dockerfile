FROM ubuntu:24.04

# NOTE:
# python:3.11.4-bookworm とかを使った場合，Selenium を同時に複数動かせないので，
# Ubuntu イメージを使う

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    curl \
    ca-certificates \
    build-essential \
    git

RUN curl -O https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    language-pack-ja \
    ./google-chrome-stable_current_amd64.deb

ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/root/.local/bin/:$PATH"

ENV UV_LINK_MODE=copy

USER ubuntu
WORKDIR /opt/e-ink_weather

ADD https://astral.sh/uv/install.sh /uv-installer.sh

RUN sh /uv-installer.sh && rm /uv-installer.sh

# NOTE: uv で Python をインストールする
RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-editable

RUN locale-gen en_US.UTF-8
RUN locale-gen ja_JP.UTF-8

ARG IMAGE_BUILD_DATE
ENV IMAGE_BUILD_DATE=${IMAGE_BUILD_DATE}

ENV TZ=Asia/Tokyo \
    LANG=ja_JP.UTF-8 \
    LANGUAGE=ja_JP:ja \
    LC_ALL=ja_JP.UTF-8

COPY font /usr/share/fonts/

COPY . .

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

CMD ["./src/display_image.py"]
