#!/usr/bin/env bash
# Cost guardrails for the student subscription. Monthly budget $100.
# Creates an $80 actual-cost budget with email alert.
# Usage: SUB_ID=xxx ALERT_EMAIL=you@school.edu ./infra/budget.sh
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
