#!/usr/bin/env zsh

APP_NAME="visionect-display"

set -e

cd $(dirname $(dirname $0))

docker build --quiet . -t ${APP_NAME}
docker run \
       --name ${APP_NAME}-$(head -c 10 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | cut -c 1-4) \
       --rm ${APP_NAME}
