#!/bin/sh
set -eu
TAG="dime-data-20260929"
URL="https://github.com/mythiipanda/dime/releases/download/${TAG}/dime_data.zip"
SHA256="54e2f5a9998844045460cd02eaabe1afe7af3f97ef96278e6de6ae89237c19a2"
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
curl -fL -o "$TMP/dime_data.zip" "$URL"
ACTUAL="$(sha256sum "$TMP/dime_data.zip" | awk '{print $1}')"
if [ "$ACTUAL" != "$SHA256" ]; then
  echo "fetch-data: checksum mismatch (got $ACTUAL)" >&2
  exit 1
fi
unzip -q -o "$TMP/dime_data.zip" -d backend
ls -la backend/data/warehouse.duckdb
echo "fetch-data: warehouse ready at backend/data/warehouse.duckdb"
