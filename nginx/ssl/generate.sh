#!/usr/bin/env bash
# Run once to generate a self-signed certificate for IP-based HTTPS access.
# Replace 192.168.1.50 with your actual server IP.
#
# Usage:  cd nginx/ssl && bash generate.sh 192.168.1.50

IP="${1:-192.168.1.50}"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout key.pem -out cert.pem \
    -subj "/CN=${IP}" \
    -addext "subjectAltName=IP:${IP}"

echo "Generated cert.pem and key.pem for IP: ${IP}"
