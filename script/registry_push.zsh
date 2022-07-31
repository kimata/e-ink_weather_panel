#!/usr/bin/env zsh

NAME=e-ink_weather_panel
REGISTRY=registry.green-rabbit.net/library

git push
docker build . -t ${NAME}
docker tag e-ink_weather_panel ${REGISTRY}/${NAME}
docker push ${REGISTRY}/${NAME}
