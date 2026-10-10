#!/bin/sh
set -eu

# Render mounts persistent disks at runtime, after the image has been built.
# Prepare only the mount root; existing app-owned files remain untouched.
if [ -d /var/data ]; then
    chown app:app /var/data
    chmod 0700 /var/data
fi

exec setpriv --reuid=app --regid=app --init-groups "$@"
