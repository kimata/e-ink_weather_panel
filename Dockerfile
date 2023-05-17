FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y language-pack-ja
RUN apt-get install -y python3 python3-pip

RUN apt-get install -y python3-docopt
RUN apt-get install -y python3-yaml python3-coloredlogs
RUN apt-get install -y python3-pil python3-matplotlib python3-pandas
RUN apt-get install -y python3-opencv
RUN apt-get install -y python3-paramiko

RUN apt-get install -y curl
RUN curl -O  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb                                                                                                                                          

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
