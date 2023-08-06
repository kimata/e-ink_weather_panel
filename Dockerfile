FROM python:3.11.4-bookworm as build

ENV TZ=Asia/Tokyo

# NOTE: libgl1-mesa-glx は OpenCV に必要
RUN apt-get update && apt-get install --assume-yes --no-install-recommends --no-install-suggests \
    gcc \
    curl \
    python3 \
    python3-dev \
    locales \
    chromium \
 && apt-get clean \
 && rm -rf /va/rlib/apt/lists/*

WORKDIR /opt/e-ink_weather

RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

COPY pyproject.toml .

RUN poetry config virtualenvs.create false \
 && poetry install \
 && rm -rf ~/.cache

RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen \
 && sed -i -e 's/# ja_JP.UTF-8 UTF-8/ja_JP.UTF-8 UTF-8/' /etc/locale.gen \
 && dpkg-reconfigure --frontend=noninteractive locales

FROM python:3.11.4-slim-bookworm as prod

COPY --from=build /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=build /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu
COPY --from=build /usr/lib/locale/locale-archive /usr/lib/locale/locale-archive

WORKDIR /opt/e-ink_weather

ENV PATH="/root/.local/bin:$PATH"

RUN useradd -m ubuntu

RUN mkdir -p data
RUN chown -R ubuntu:ubuntu .

USER ubuntu

COPY font /usr/share/fonts/
COPY --chown=ubuntu . .

CMD ["./app/display_image.py"]
