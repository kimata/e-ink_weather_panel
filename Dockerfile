FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN curl -O  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb

RUN apt-get update && apt-get install -y \
    language-pack-ja \
    python3 python3-pip \
    ./google-chrome-stable_current_amd64.deb \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/e-ink_weather

RUN locale-gen en_US.UTF-8
RUN locale-gen ja_JP.UTF-8

COPY font /usr/share/fonts/

RUN useradd -m ubuntu

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

USER ubuntu

# NOTE: apt にあるものはバージョンが古いので直接入れる
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/home/ubuntu/.local/bin:$PATH"

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

CMD ["./app/display_image.py"]
