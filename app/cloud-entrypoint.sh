#!/bin/sh
set -eu
# Render mounts persistent disks at startup, after image-time ownership changes.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /data
    chown bobhead:bobhead /data
    chmod 700 /data
    exec gosu bobhead "$@"
fi
exec "$@"
