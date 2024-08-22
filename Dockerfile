FROM ubuntu:22.04

# NOTE:
# python:3.11.4-bookworm とかを使った場合，Selenium を同時に複数動かせないので，
# Ubuntu イメージを使う

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    curl \
    ca-certificates

RUN curl -O https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

RUN --mount=type=cache,target=/var/lib/apt,sharing=locked \
    --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get update && apt-get install --no-install-recommends --assume-yes \
    python3 \
    python3-dev \
    language-pack-ja \
    ./google-chrome-stable_current_amd64.deb

ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/root/.rye/shims/:$PATH

RUN curl -sSf https://rye.astral.sh/get | RYE_NO_AUTO_INSTALL=1 RYE_INSTALL_OPTION="--yes" bash

RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    --mount=type=bind,source=README.md,target=README.md \
    rye lock

RUN --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=README.md,target=README.md \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.lock


ARG IMAGE_BUILD_DATE

ENV TZ=Asia/Tokyo
ENV IMAGE_BUILD_DATE=${IMAGE_BUILD_DATE}

RUN locale-gen en_US.UTF-8
RUN locale-gen ja_JP.UTF-8

WORKDIR /opt/e-ink_weather


COPY font /usr/share/fonts/

RUN useradd -m ubuntu

COPY . .

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

USER ubuntu

CMD ["./src/display_image.py"]
