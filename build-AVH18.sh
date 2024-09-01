#!/bin/sh

set -e

docker build -t pioneer-firmware-builder .

docker run --rm -it -v ./data:/data pioneer-firmware-builder \
    AVH18.img AVH18 AVH18.zip CVJ2547-E-extdata.tar CVJ2547-E-cache.tar --variant 1
