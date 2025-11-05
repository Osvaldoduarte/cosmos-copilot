#!/bin/bash
# Script de deploy do ChromaDB Server v1.2.2 no Cloud Run com PostgreSQL

set -e # Sai em caso de erro

PROJECT_ID="gen-lang-client-0750608840"
REGION="us-central1"
SERVICE_NAME="chroma-server"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
SQL_INSTANCE_CONNECTION_NAME="${PROJECT_ID}:${REGION}:cosmos-copilot-postgres" # Ajuste se região/nome do SQL for diferente
DB_SECRET_NAME="POSTGRES_PASSWORD" # Nome do secret com a senha do PG
DB_SECRET_VERSION="latest"

# Cores
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${GREEN}🚀 Iniciando deploy do ChromaDB Server v1.2.2 com PostgreSQL${NC}"

# 1. Build da imagem
echo -e "\n${YELLOW}📦 Construindo imagem Docker...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}:latest .
if [ $? -ne 0 ]; then echo -e "${RED}❌ Falha no build${NC}"; exit 1; fi
echo -e "${GREEN}✅ Imagem construída${NC}"

# 2. Deploy no Cloud Run
echo -e "\n${YELLOW}🚢 Fazendo deploy no Cloud Run com Cloud SQL...${NC}"
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME}:latest \
  --platform managed \
  --region ${REGION} \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 3 \
  --min-instances 0 \
  --port 8000 \
  --add-cloudsql-instances ${SQL_INSTANCE_CONNECTION_NAME} \
  --update-secrets=/run/secrets/${DB_SECRET_NAME}=${DB_SECRET_NAME}:${DB_SECRET_VERSION} \
  --set-env-vars=CHROMA_DB_IMPL=duckdb+pg,\
CHROMA_DB_PG_HN_HOST=${SQL_INSTANCE_CONNECTION_NAME},\
CHROMA_DB_PG_HN_PORT=5432,\
CHROMA_DB_PG_HN_DATABASE=postgres,\
CHROMA_DB_PG_HN_USER=chroma_user,\
CHROMA_DB_PG_HN_PASSWORD=/run/secrets/${DB_SECRET_NAME}

if [ $? -ne 0 ]; then echo -e "${RED}❌ Falha no deploy${NC}"; exit 1; fi
echo -e "${GREEN}✅ Deploy concluído com persistência PG!${NC}"

if [ $? -ne 0 ]; then echo -e "${RED}❌ Falha no deploy${NC}"; exit 1; fi
echo -e "${GREEN}✅ Deploy concluído!${NC}"

# 3. Obtém URL e Testa
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')
echo -e "\n${GREEN}🌐 Serviço disponível em: ${SERVICE_URL}${NC}"
echo -e "${YELLOW}📝 Configure CHROMA_HOST=${SERVICE_URL} nos clientes${NC}"
echo -e "\n${YELLOW}🔍 Testando heartbeat...${NC}"
sleep 5
if curl -sf "${SERVICE_URL}/api/v1/heartbeat"; then
  echo -e "\n${GREEN}✅ Servidor respondendo ao heartbeat!${NC}"
else
  echo -e "\n${RED}⚠️ Servidor NÃO respondeu ao heartbeat. Verifique os logs:${NC}"
  echo "gcloud run services logs tail ${SERVICE_NAME} --region ${REGION}"
  exit 1
fi

echo -e "\n${YELLOW}📊 Para ver logs:${NC}"
echo "gcloud run services logs tail ${SERVICE_NAME} --region ${REGION}"