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
WAREHOUSE_URL="${DIME_WAREHOUSE_URL:-https://dimewarehouse.blob.core.windows.net/warehouse/dime_data_full.zip}"
if fetch "$WAREHOUSE_URL" "5566409dd71881194edc6dd6ddddbf56a316824a9c34340b3ddb34d6c7a95ea8" "dime-data-20260930"; then
  :
else
  echo "fetch-data: download failed" >&2
  exit 1
fi
unzip -q -o "$TMP/dime_data.zip" -d backend
ls -la backend/data/warehouse.duckdb
echo "fetch-data: warehouse ready at backend/data/warehouse.duckdb"
