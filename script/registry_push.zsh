#!/usr/bin/env zsh

NAME=e-ink_weather_panel
REGISTRY=registry.green-rabbit.net/library

git push
docker build . -t ${NAME}
docker tag ${NAME} ${REGISTRY}/${NAME}
docker push ${REGISTRY}/${NAME}
