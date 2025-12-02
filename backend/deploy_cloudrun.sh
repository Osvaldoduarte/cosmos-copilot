#!/bin/bash

# Script para fazer deploy do backend no Google Cloud Run

set -e  # Exit on error

echo "======================================================================"
echo "🚀 DEPLOY DO BACKEND NO GOOGLE CLOUD RUN"
echo "======================================================================"

# Configurações
PROJECT_ID="gen-lang-client-0750608840"
SERVICE_NAME="cosmos-backend"
REGION="us-central1"
IMAGE_NAME="gcr.io/${PROJECT_ID}/backend"

echo ""
echo "📋 Configurações:"
echo "   Projeto: ${PROJECT_ID}"
echo "   Serviço: ${SERVICE_NAME}"
echo "   Região: ${REGION}"
echo "   Imagem: ${IMAGE_NAME}"

# Verifica se gcloud está instalado
if ! command -v gcloud &> /dev/null; then
    echo ""
    echo "❌ Google Cloud SDK não está instalado!"
    echo "📦 Instale com: brew install --cask google-cloud-sdk"
    exit 1
fi

echo ""
echo "✅ Google Cloud SDK encontrado"

# Verifica se está autenticado
echo ""
echo "🔐 Verificando autenticação..."
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo "❌ Não está autenticado no Google Cloud"
    echo "🔑 Execute: gcloud auth login"
    exit 1
fi

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
echo "✅ Autenticado como: ${ACCOUNT}"

# Define o projeto
echo ""
echo "⚙️  Configurando projeto..."
gcloud config set project ${PROJECT_ID}

# Habilita APIs necessárias
echo ""
echo "🔧 Habilitando APIs necessárias..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build da imagem
echo ""
echo "======================================================================"
echo "🏗️  CONSTRUINDO IMAGEM DOCKER"
echo "======================================================================"

cd "$(dirname "$0")"

gcloud builds submit --tag ${IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro ao construir imagem!"
    exit 1
fi

echo ""
echo "✅ Imagem construída com sucesso!"

# Deploy no Cloud Run
echo ""
echo "======================================================================"
echo "🚀 FAZENDO DEPLOY NO CLOUD RUN"
echo "======================================================================"

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 1 \
    --set-env-vars "EVOLUTION_API_URL=${EVOLUTION_API_URL},EVOLUTION_INSTANCE_NAME=${EVOLUTION_INSTANCE_NAME},EVOLUTION_API_KEY=${EVOLUTION_API_KEY},SECRET_KEY=${SECRET_KEY},DATABASE_URL=${DATABASE_URL},REDIS_URL=${REDIS_URL},CHROMA_SERVER_URL=${CHROMA_SERVER_URL}"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro ao fazer deploy!"
    exit 1
fi

# Obtém URL do serviço
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format="value(status.url)")

echo ""
echo "======================================================================"
echo "🌍 CONFIGURANDO PUBLIC_URL"
echo "======================================================================"
echo "Definindo PUBLIC_URL=${SERVICE_URL}..."

gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --update-env-vars "PUBLIC_URL=${SERVICE_URL}"

echo ""
echo "======================================================================"
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "======================================================================"
echo ""
echo "🌐 URL do Backend: ${SERVICE_URL}"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo ""
echo "1. O webhook será configurado AUTOMATICAMENTE na inicialização!"
echo "   (Verifique os logs do Cloud Run para confirmar)"
echo ""
echo "2. Atualize o frontend para usar esta URL:"
echo "   API_BASE_URL = '${SERVICE_URL}'"
echo "   WS_URL = '${SERVICE_URL}/ws' (use wss:// para HTTPS)"
echo ""
echo "======================================================================"

# Salva URL em arquivo
echo "${SERVICE_URL}" > backend_url.txt
echo "💾 URL salva em: backend_url.txt"
