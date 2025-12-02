import sys
import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load env
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, 'backend', '.env'))
load_dotenv(os.path.join(base_dir, '.env'))

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")
INSTANCE = "cosmos-wpp-osvaldo"
WEBHOOK_URL = "https://cosmos-backend-129644477821.us-central1.run.app/webhook/evolution"

async def configure_webhook():
    print(f"🔧 Configurando webhook para instance: {INSTANCE}")
    print(f"   Webhook URL: {WEBHOOK_URL}")
    
    headers = {"apikey": EVO_TOKEN, "Content-Type": "application/json"}
    
    payload = {
        "webhook": {
            "enabled": True,
            "url": WEBHOOK_URL,
            "webhookByEvents": False,
            "webhookBase64": False,
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
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{EVO_URL}/webhook/set/{INSTANCE}",
                headers=headers,
                json=payload
            )
            
            if resp.status_code in [200, 201]:
                print(f"\n✅ Webhook configurado com sucesso!")
                print(f"   Todas as mensagens que chegarem no WhatsApp agora vão sincronizar!")
                print(f"\n📱 Teste: Envie uma mensagem pelo WhatsApp e veja aparecer no app")
            else:
                print(f"\n❌ Erro ao configurar webhook: {resp.status_code}")
                print(f"   Response: {resp.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(configure_webhook())
