#!/bin/bash
# First-time Let's Encrypt certificate setup.
# Run once from the project root: bash nginx/init-letsencrypt.sh
set -e

# Load DOMAIN and LETSENCRYPT_EMAIL from .env
set -a; source .env; set +a

if [ -z "$DOMAIN" ] || [ -z "$LETSENCRYPT_EMAIL" ]; then
    echo "ERROR: Set DOMAIN and LETSENCRYPT_EMAIL in .env before running this script."
    exit 1
fi

CERT_DIR="./data/certbot/conf/live/$DOMAIN"

echo "==> Domain: $DOMAIN"
echo "==> Email:  $LETSENCRYPT_EMAIL"

# Create webroot challenge directory
mkdir -p ./data/certbot/www/.well-known/acme-challenge
mkdir -p "$CERT_DIR"

echo ""
echo "==> Creating temporary self-signed certificate so nginx can start..."
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$DOMAIN" 2>/dev/null

echo ""
echo "==> Starting web and nginx..."
docker compose up -d web nginx
echo "    Waiting 5s for nginx to be ready..."
sleep 5

echo ""
echo "==> Requesting Let's Encrypt certificate..."
docker compose run --rm certbot

echo ""
echo "==> Reloading nginx with the real certificate..."
docker compose exec nginx nginx -s reload

echo ""
echo "==> Done! Certificate obtained for $DOMAIN."
echo ""
echo "    To renew (run periodically, e.g. via cron):"
echo "      docker compose run --rm certbot renew && docker compose exec nginx nginx -s reload"
