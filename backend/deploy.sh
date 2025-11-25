#!/bin/bash

# Script de deploy para Google Cloud Run
# Baseado no comando fornecido pelo usuário

set -e  # Exit on error

echo "======================================================================"
echo "🚀 DEPLOY DO BACKEND NO GOOGLE CLOUD RUN"
echo "======================================================================"

# Configurações (extraídas do seu comando)
PROJECT_ID="gen-lang-client-0750608840"
REGION="us-central1"
REPOSITORY="cloud-run-source-deploy"
IMAGE_NAME="cosmos-backend"
TAG="latest"
SERVICE_NAME="cosmos-backend"

FULL_IMAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:${TAG}"

echo ""
echo "📋 Configurações:"
echo "   Projeto: ${PROJECT_ID}"
echo "   Região: ${REGION}"
echo "   Imagem: ${FULL_IMAGE_PATH}"
echo "   Serviço: ${SERVICE_NAME}"

# Verifica se está no diretório correto
if [ ! -f "main.py" ]; then
    echo ""
    echo "❌ Erro: Execute este script do diretório backend/"
    echo "   cd backend && ./deploy.sh"
    exit 1
fi

echo ""
echo "======================================================================"
echo "🏗️  CONSTRUINDO E ENVIANDO IMAGEM"
echo "======================================================================"

# Build e push da imagem usando o comando fornecido
gcloud builds submit . --tag ${FULL_IMAGE_PATH}

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro ao construir imagem!"
    exit 1
fi

echo ""
echo "✅ Imagem construída e enviada com sucesso!"

# Deploy no Cloud Run
echo ""
echo "======================================================================"
echo "🚀 FAZENDO DEPLOY NO CLOUD RUN"
echo "======================================================================"

# Carrega variáveis de ambiente do .env
if [ -f "../.env" ]; then
    echo "📄 Carregando variáveis de ambiente do .env..."
    export $(cat ../.env | grep -v '^#' | xargs)
else
    echo "⚠️  Arquivo .env não encontrado!"
fi

gcloud run deploy ${SERVICE_NAME} \
    --image ${FULL_IMAGE_PATH} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "EVOLUTION_API_URL=${EVOLUTION_API_URL},EVOLUTION_INSTANCE_NAME=${EVOLUTION_INSTANCE_NAME},EVOLUTION_API_KEY=${EVOLUTION_API_KEY},SECRET_KEY=${SECRET_KEY}"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro ao fazer deploy!"
    exit 1
fi

# Obtém URL do serviço
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format="value(status.url)")

echo ""
echo "======================================================================"
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "======================================================================"
echo ""
echo "🌐 URL do Backend: ${SERVICE_URL}"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo ""
echo "1. Configure o webhook na Evolution API:"
echo "   URL: ${SERVICE_URL}/webhook/evolution"
echo ""
echo "   Execute:"
echo "   cd backend"
echo "   source .venv/bin/activate"
echo "   python configure_production_webhook.py"
echo ""
echo "2. Atualize o frontend para usar esta URL:"
echo "   API_BASE_URL = '${SERVICE_URL}'"
echo "   WS_URL = 'wss://${SERVICE_URL#https://}/ws'"
echo ""
echo "3. Teste enviando uma mensagem do WhatsApp"
echo ""
echo "======================================================================"

# Salva URL em arquivo
echo "${SERVICE_URL}" > backend_url.txt
echo "💾 URL salva em: backend_url.txt"
