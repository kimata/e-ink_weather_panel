#!/usr/bin/env zsh

set -e

docker build . -t visionect-display
docker run --rm -it visionect-display
