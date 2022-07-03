#!/usr/bin/env zsh

APP_NAME="visionect-display"

set -e

cd $(dirname $(dirname $0))

docker build --quiet . -t ${APP_NAME}
docker run --rm -it ${APP_NAME}
