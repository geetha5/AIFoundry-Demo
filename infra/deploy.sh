#!/usr/bin/env bash
# Deploys/updates the chat + embedding model deployments on an Azure AI
# Foundry resource, then deploys the app container to Azure Container Apps
# in the given environment (staging or prod).
#
# Usage:
#   ./infra/deploy.sh <environment> <image-tag>
#
# Required env vars (set as GitHub secrets, injected by the workflow):
#   AZURE_RESOURCE_GROUP
#   AZURE_FOUNDRY_RESOURCE_NAME
#   AZURE_CONTAINER_APP_NAME_STAGING
#   AZURE_CONTAINER_APP_NAME_PROD
#   AZURE_CONTAINER_REGISTRY

set -euo pipefail

ENVIRONMENT="${1:?Usage: deploy.sh <environment> <image-tag>}"
IMAGE_TAG="${2:?Usage: deploy.sh <environment> <image-tag>}"

if [[ "$ENVIRONMENT" == "staging" ]]; then
  APP_NAME="$AZURE_CONTAINER_APP_NAME_STAGING"
elif [[ "$ENVIRONMENT" == "prod" ]]; then
  APP_NAME="$AZURE_CONTAINER_APP_NAME_PROD"
else
  echo "Unknown environment: $ENVIRONMENT (expected staging or prod)"
  exit 1
fi

echo "== Ensuring Foundry model deployments exist =="
az cognitiveservices account deployment create \
  --name "$AZURE_FOUNDRY_RESOURCE_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --deployment-name "chat-deployment" \
  --model-name "gpt-4o-mini" \
  --model-version "2024-07-18" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --sku-capacity 1 \
  || echo "chat-deployment already exists, skipping"

az cognitiveservices account deployment create \
  --name "$AZURE_FOUNDRY_RESOURCE_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --deployment-name "embedding-deployment" \
  --model-name "text-embedding-3-small" \
  --model-version "1" \
  --model-format OpenAI \
  --sku-name "Standard" \
  --sku-capacity 1 \
  || echo "embedding-deployment already exists, skipping"

echo "== Deploying app image to $ENVIRONMENT ($APP_NAME) =="
az containerapp update \
  --name "$APP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --image "$AZURE_CONTAINER_REGISTRY/rag-demo:$IMAGE_TAG"

echo "== Fetching endpoint URL =="
az containerapp show \
  --name "$APP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv
