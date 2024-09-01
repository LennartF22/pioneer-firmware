#!/bin/sh

set -e

docker build -t pioneer-firmware-builder .

docker run --rm -it -v ./data:/data pioneer-firmware-builder \
    AVH19.img AVH19 AVH19.zip CVJ3973-A-extdata.tar CVJ3973-A-cache.tar --variant 1
