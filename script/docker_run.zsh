#!/usr/bin/env zsh

set -e

cd $(dirname $(dirname $0))

docker build . -t visionect-display
docker run --rm -it visionect-display
