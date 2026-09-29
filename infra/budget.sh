#!/usr/bin/env bash
set -euo pipefail

SUB_ID="${SUB_ID:?set SUB_ID}"
ALERT_EMAIL="${ALERT_EMAIL:?set ALERT_EMAIL}"
RG="${RG:-dime-rg}"

az account set -s "$SUB_ID"
az consumption budget create -g "$RG" \
  --budget-name dime-monthly-cap \
  --amount 80 --time-grain Monthly \
  --category Cost \
  --notifications "Alert80=80,contact-emails=$ALERT_EMAIL" \
  -o none
echo "budget set: \$80 of \$100 with alert to $ALERT_EMAIL"
