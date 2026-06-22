#!/bin/sh
# Generates a self-signed TLS certificate for development.
# In production replace with a real cert (Let's Encrypt / your CA).
set -e
CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/server.crt" ] && [ -f "$CERT_DIR/server.key" ]; then
  echo "Certificates already exist, skipping."
  exit 0
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -subj "/C=BY/ST=Minsk/L=Minsk/O=ASR/CN=localhost"

echo "Self-signed certificate generated at $CERT_DIR"
