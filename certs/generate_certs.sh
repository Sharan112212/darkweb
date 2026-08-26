#!/bin/bash
# Generates ONE self-signed cert/key pair that gets mounted into BOTH
# nginx-hidden and nginx-clearnet. This is what makes the two sites
# provably linkable by certificate fingerprint — the planted misconfig
# your infra-matcher module is built to catch.
#
# Run this once before `docker compose up`.

set -e
cd "$(dirname "$0")"

MSYS_NO_PATHCONV=1 openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout shared_key.pem \
  -out shared_cert.pem \
  -days 365 \
  -subj "/C=IN/O=TechCorp Cloud Solutions/CN=techcorp-cloud.example"

echo ""
echo "Certificate generated. Fingerprint (this is what your matcher compares):"
openssl x509 -in shared_cert.pem -noout -fingerprint -sha256
