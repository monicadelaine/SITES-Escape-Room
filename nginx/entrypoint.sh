#!/bin/sh
set -e

if [ ! -f /etc/nginx/ssl/cert.pem ]; then
    echo "Generating self-signed SSL certificate..."
    mkdir -p /etc/nginx/ssl
    openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
        -keyout /etc/nginx/ssl/key.pem \
        -out /etc/nginx/ssl/cert.pem \
        -subj "/CN=localhost"
    echo "Certificate generated."
fi

exec "$@"
