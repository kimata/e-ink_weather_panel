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
    python3-docopt \
    python3-yaml python3-coloredlogs \
    python3-pil python3-matplotlib python3-pandas \
    python3-opencv \
    python3-paramiko \
    curl \
    ./google-chrome-stable_current_amd64.deb \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/e-ink_weather

COPY requirements.txt .
RUN pip3 install -r requirements.txt

RUN locale-gen en_US.UTF-8

RUN useradd -m ubuntu

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

USER ubuntu

COPY font /usr/share/fonts/
COPY --chown=ubuntu . .

CMD ["./src/display_image.py"]
