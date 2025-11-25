#!/bin/bash

# Script para iniciar ngrok e configurar webhook automaticamente

echo "======================================================================"
echo "🚀 CONFIGURAÇÃO AUTOMÁTICA DE WEBHOOK"
echo "======================================================================"

# Verifica se ngrok está instalado
if ! command -v ngrok &> /dev/null; then
    echo ""
    echo "❌ Ngrok não está instalado!"
    echo ""
    echo "📦 Instalando ngrok..."
    brew install ngrok
    
    if [ $? -ne 0 ]; then
        echo "❌ Erro ao instalar ngrok"
        echo "💡 Instale manualmente: brew install ngrok"
        exit 1
    fi
fi

echo ""
echo "✅ Ngrok está instalado"

# Verifica se ngrok já está rodando
if curl -s http://localhost:4040/api/tunnels &> /dev/null; then
    echo "✅ Ngrok já está rodando"
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)
    echo "   URL: $NGROK_URL"
else
    echo ""
    echo "🔌 Iniciando ngrok..."
    echo "⚠️  Uma nova janela será aberta. NÃO FECHE!"
    
    # Inicia ngrok em background
    osascript -e 'tell app "Terminal" to do script "ngrok http 8000"'
    
    echo ""
    echo "⏳ Aguardando ngrok iniciar (10 segundos)..."
    sleep 10
    
    # Tenta obter URL do ngrok
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null)
    
    if [ -z "$NGROK_URL" ]; then
        echo "❌ Não foi possível obter URL do ngrok"
        echo "💡 Verifique se o ngrok iniciou corretamente"
        exit 1
    fi
    
    echo "✅ Ngrok iniciado: $NGROK_URL"
fi

echo ""
echo "======================================================================"
echo "⚙️  CONFIGURANDO WEBHOOK NA EVOLUTION API"
echo "======================================================================"

# Ativa ambiente virtual e executa script de configuração
cd "$(dirname "$0")"
source .venv/bin/activate

# Cria script Python temporário para configurar webhook
cat > /tmp/configure_webhook.py << 'EOF'
import os
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")

# Obtém URL do ngrok
response = requests.get("http://localhost:4040/api/tunnels")
ngrok_url = response.json()['tunnels'][0]['public_url']

print(f"📡 URL do Ngrok: {ngrok_url}")

# Configura webhook
headers = {
    "apikey": EVO_TOKEN,
    "Content-Type": "application/json"
}

webhook_config = {
    "webhook": {
        "url": f"{ngrok_url}/webhook/evolution",
        "webhook_by_events": False,
        "webhook_base64": False,
        "events": [
            "QRCODE_UPDATED",
            "MESSAGES_UPSERT",
            "MESSAGES_UPDATE",
            "MESSAGES_DELETE",
            "SEND_MESSAGE",
            "CONNECTION_UPDATE"
        ]
    }
}

print(f"📤 Configurando webhook...")
response = requests.post(
    f"{EVO_URL}/webhook/set/{EVO_INSTANCE}",
    headers=headers,
    json=webhook_config,
    timeout=10
)

if response.status_code in [200, 201]:
    print(f"✅ Webhook configurado com sucesso!")
    print(f"   URL: {ngrok_url}/webhook/evolution")
else:
    print(f"❌ Erro ao configurar webhook!")
    print(f"   Status: {response.status_code}")
    print(f"   Resposta: {response.text}")
EOF

# Move script para o diretório correto
mv /tmp/configure_webhook.py .

# Executa configuração
python configure_webhook.py

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================================================"
    echo "✅ CONFIGURAÇÃO CONCLUÍDA!"
    echo "======================================================================"
    echo ""
    echo "🧪 Teste agora:"
    echo "   1. Envie uma mensagem do WhatsApp"
    echo "   2. A mensagem deve aparecer no frontend em tempo real!"
    echo ""
    echo "⚠️  IMPORTANTE:"
    echo "   - NÃO FECHE a janela do ngrok"
    echo "   - Se fechar, execute este script novamente"
    echo ""
else
    echo ""
    echo "======================================================================"
    echo "❌ ERRO NA CONFIGURAÇÃO"
    echo "======================================================================"
    echo ""
    echo "💡 Tente executar manualmente:"
    echo "   cd backend"
    echo "   source .venv/bin/activate"
    echo "   python setup_webhook.py"
fi

# Limpa arquivo temporário
rm -f configure_webhook.py
