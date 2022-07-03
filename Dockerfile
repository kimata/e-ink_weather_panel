FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y language-pack-ja
RUN apt-get install -y python3
RUN apt-get install -y python3-yaml python3-lxml
RUN apt-get install -y python3-influxdb
RUN apt-get install -y python3-pil python3-opencv python3-matplotlib python3-pandas
RUN apt-get install -y python3-requests

RUN locale-gen en_US.UTF-8

WORKDIR /opt/visionect_display
COPY . .

CMD ["./src/update.py"]
