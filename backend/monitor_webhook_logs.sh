#!/bin/bash

PROJECT_ID="gen-lang-client-0750608840"
SERVICE_NAME="cosmos-backend"
REGION="us-central1"

echo "🔍 Monitorando logs do Cloud Run em tempo real..."
echo "📱 ENVIE UMA MENSAGEM PELO WHATSAPP AGORA!"
echo "---"

gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
    --project=${PROJECT_ID} \
    --format="value(timestamp,textPayload,httpRequest.requestUrl)" \
    --filter="httpRequest.requestUrl=~webhook OR textPayload=~webhook OR textPayload=~Webhook"
