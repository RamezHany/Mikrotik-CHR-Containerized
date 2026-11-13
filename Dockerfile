# MikroTik RouterOS CHR in Docker via QEMU — Ramez Hany's own image.
# PLAIN vanilla CHR: the RouterOS binary comes ONLY from MikroTik's official
# download server at build time, checksum-verified. Branding, default user
# and password are NOT baked in — they are applied after deploy by
# provision.py (owner decision 2026-11-12: vanilla image + provisioning
# script, instead of a pre-branded golden disk).
FROM alpine:3.24

LABEL org.opencontainers.image.authors="Ramez Hany <ramzh06@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/RamezHany/mikrotik-chr-containerized"
LABEL org.opencontainers.image.description="MikroTik RouterOS CHR running inside Docker using QEMU"

ARG ROUTEROS_VERSION=7.20.4
ARG ROUTEROS_SHA256=7c1420075d27d1e72b132faf39805fc171e558b2ab8d54629bf4fc7bf7e44967

ENV ROUTEROS_VERSION=$ROUTEROS_VERSION
ENV ROUTEROS_IMAGE=chr-$ROUTEROS_VERSION.vdi
ENV ROUTEROS_URL=https://download.mikrotik.com/routeros/$ROUTEROS_VERSION/chr-$ROUTEROS_VERSION.vdi.zip

RUN apk add --no-cache \
    wget unzip \
    qemu-system-x86_64 qemu-img \
    iproute2 bridge-utils iptables \
    bash

RUN mkdir -p /routeros/data && \
    wget --timeout=60 --tries=3 "${ROUTEROS_URL}" -O /routeros/image.zip && \
    printf '%s  /routeros/image.zip\n' "$ROUTEROS_SHA256" | sha256sum -c - && \
    unzip /routeros/image.zip -d /routeros && \
    rm -f /routeros/image.zip

WORKDIR /routeros
COPY entrypoint.sh /routeros/entrypoint.sh
RUN chmod +x /routeros/entrypoint.sh

VOLUME ["/routeros/data"]
ENTRYPOINT ["/routeros/entrypoint.sh"]
