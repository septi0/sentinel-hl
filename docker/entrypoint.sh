#!/bin/sh
set -e

if ! [ -f /ssh_keys/id_ed25519 ]; then
    ssh-keygen -q -N "" -t ed25519 -f /ssh_keys/id_ed25519 -C "Sentinel Hl"

    echo "SSH key pair created. Public key: $(cat /ssh_keys/id_ed25519.pub)"
fi

exec /usr/local/bin/sentinel-hl "$@"