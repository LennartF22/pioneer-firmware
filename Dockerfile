FROM debian:trixie-slim
RUN apt update \
    && apt install --no-install-recommends -y python3 fdisk e2fsprogs libarchive13t64 android-sdk-libsparse-utils \
    && rm -rf /var/lib/apt/lists/*
COPY builder.py /app/
VOLUME /data
WORKDIR /data
ENTRYPOINT ["/app/builder.py"]
