#!/bin/sh
# Auto-generate a self-signed cert if none exists, then start nginx normally.
set -e

CERT=/etc/nginx/ssl/cert.pem
KEY=/etc/nginx/ssl/key.pem

if [ ! -f "$CERT" ] || [ ! -f "$KEY" ]; then
    echo "==> No SSL certificate found — generating self-signed cert..."
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout "$KEY" -out "$CERT" \
        -subj "/CN=localhost" 2>/dev/null
    echo "==> Self-signed certificate created."
fi

# Hand off to the official nginx entrypoint
exec /docker-entrypoint.sh "$@"
