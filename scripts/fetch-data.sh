#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
fetch() {
  if curl -fL -o "$TMP/dime_data.zip" "$1"; then
    ACTUAL="$(sha256sum "$TMP/dime_data.zip" | awk '{print $1}')"
    if [ "$ACTUAL" = "$2" ]; then
      echo "fetch-data: using $3"
      return 0
    fi
    echo "fetch-data: checksum mismatch for $3 (got $ACTUAL)" >&2
  fi
  return 1
}
if fetch "https://github.com/mythiipanda/dime/releases/download/dime-data-20260929/dime_data.zip" "54e2f5a9998844045460cd02eaabe1afe7af3f97ef96278e6de6ae89237c19a2" "dime-data-20260929"; then
  :
else
  echo "fetch-data: download failed" >&2
  exit 1
fi
unzip -q -o "$TMP/dime_data.zip" -d backend
ls -la backend/data/warehouse.duckdb
echo "fetch-data: warehouse ready at backend/data/warehouse.duckdb"
