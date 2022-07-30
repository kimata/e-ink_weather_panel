#!/usr/bin/env zsh

REGISTRY=registry.green-rabbit.net
NAME=library/e-ink_weather_panel

docker tag e-ink_weather_panel ${REGISTRY}/${NAME}
docker push ${REGISTRY}/${NAME}
