#!/usr/bin/env bash
# Dime backend deploy to Azure Container Apps, consumption plan.
# Stays inside student credits: scale to zero, tiny CPU, capped replicas.
# Usage: RG=dime-rg LOC=eastus APP=dime-backend ./infra/deploy.sh
# Requires: az login, backend/.env present (keys stay local, pushed as secrets).
set -euo pipefail

RG="${RG:-dime-rg}"
LOC="${LOC:-eastus}"
APP="${APP:-dime-backend}"
ACR="${ACR:-dimeregistry}"
ENV_NAME="${ENV_NAME:-dime-env}"
LAW="${LAW:-dime-logs}"

cd "$(dirname "$0")/../backend"
set -a; . ./.env; set +a
: "${MISTRAL_API_KEY:?missing}" "${OPENROUTER_API_KEY:?missing}"

az group create -n "$RG" -l "$LOC" -o none
az acr create -g "$RG" -n "$ACR" --sku Basic -o none 2>/dev/null || true
# Student subscriptions block ACR Tasks, so push the local image instead.
az acr login -n "$ACR" -o none
docker tag dime-backend:rewrite "$ACR.azurecr.io/$APP:latest"
docker push "$ACR.azurecr.io/$APP:latest"

WS_EXISTS=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" \
  --query name -o tsv 2>/dev/null || true)
if [ -z "$WS_EXISTS" ]; then
  WS_ID=$(az monitor log-analytics workspace create -g "$RG" -n "$LAW" \
    --retention-time 30 --query customerId -o tsv)
else
  WS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" \
    --query customerId -o tsv)
fi

ENV_EXISTS=$(az containerapp env show -g "$RG" -n "$ENV_NAME" \
  --query name -o tsv 2>/dev/null || true)
if [ -z "$ENV_EXISTS" ]; then
  az containerapp env create -g "$RG" -n "$ENV_NAME" -l "$LOC" \
    --logs-destination log-analytics \
    --logs-workspace-id "$WS_ID" -o none
fi

az acr update -g "$RG" -n "$ACR" --admin-enabled true -o none
ACR_PASS=$(az acr credential show -g "$RG" -n "$ACR" --query "passwords[0].value" -o tsv)

APP_EXISTS=$(az containerapp show -g "$RG" -n "$APP" \
  --query name -o tsv 2>/dev/null || true)
if [ -z "$APP_EXISTS" ]; then
  az containerapp create -g "$RG" -n "$APP" \
    --environment "$ENV_NAME" \
    --image "$ACR.azurecr.io/$APP:latest" \
    --registry-server "$ACR.azurecr.io" \
    --registry-username "$ACR" --registry-password "$ACR_PASS" \
    --target-port 8000 --ingress external \
    --min-replicas 0 --max-replicas 2 \
    --cpu 0.5 --memory 1.0Gi \
    --workload-profile-name Consumption \
    --secrets mistral-key="$MISTRAL_API_KEY" openrouter-key="$OPENROUTER_API_KEY" \
    --env-vars MISTRAL_API_KEY=secretref:mistral-key \
      OPENROUTER_API_KEY=secretref:openrouter-key \
      MISTRAL_MODEL=ministral-8b-2512 \
      OPENROUTER_MODEL=nvidia/nemotron-3-super-120b-a12b:free \
      CORS_ALLOWED_ORIGINS="*" \
    -o none
else
  az containerapp update -g "$RG" -n "$APP" \
    --image "$ACR.azurecr.io/$APP:latest" -o none
fi

echo "URL: $(az containerapp show -g "$RG" -n "$APP" \
  --query properties.configuration.ingress.fqdn -o tsv)"
