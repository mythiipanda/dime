#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
DATASET="${DIME_WAREHOUSE_DATASET:-mythiix/dime-warehouse}"
REVISION="${DIME_WAREHOUSE_REVISION:-main}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM
mkdir -p backend/data
base="https://huggingface.co/datasets/${DATASET}/resolve/${REVISION}"
hf_curl() {
  if [ -n "${HF_TOKEN:-}" ]; then
    curl -fL --retry 3 -H "Authorization: Bearer ${HF_TOKEN}" "$@"
  else
    curl -fL --retry 3 "$@"
  fi
}
hf_curl -o "$TMP/warehouse.duckdb.sha256" "${base}/warehouse.duckdb.sha256"
expected="$(awk '{print $1}' "$TMP/warehouse.duckdb.sha256")"
case "$expected" in
  *[!0-9a-fA-F]*) echo "fetch-data: invalid checksum in warehouse.duckdb.sha256" >&2; exit 1 ;;
esac
if [ "${#expected}" -ne 64 ]; then
  echo "fetch-data: invalid checksum length in warehouse.duckdb.sha256" >&2
  exit 1
fi
actual=""
if [ -f backend/data/warehouse.duckdb ]; then
  actual="$(sha256sum backend/data/warehouse.duckdb | awk '{print $1}')"
fi
if [ "$actual" != "$expected" ]; then
  hf_curl -o "$TMP/warehouse.duckdb" "${base}/warehouse.duckdb"
  actual="$(sha256sum "$TMP/warehouse.duckdb" | awk '{print $1}')"
  if [ "$actual" != "$expected" ]; then
    echo "fetch-data: checksum mismatch for warehouse.duckdb (got $actual)" >&2
    exit 1
  fi
  mv "$TMP/warehouse.duckdb" backend/data/warehouse.duckdb
fi
ls -la backend/data/warehouse.duckdb
echo "fetch-data: warehouse ready at backend/data/warehouse.duckdb ($expected)"
