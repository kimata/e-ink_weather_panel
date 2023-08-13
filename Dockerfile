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

RUN useradd -m ubuntu

# NOTE: apt にあるものはバージョンが古いので直接入れる
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/home/ubuntu/.local/bin:$PATH"

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

USER ubuntu

COPY font /usr/share/fonts/
COPY --chown=ubuntu . .

CMD ["./app/display_image.py"]
