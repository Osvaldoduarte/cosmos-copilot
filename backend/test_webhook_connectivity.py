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

async def test_webhook_from_evolution():
    """
    Testa se a Evolution API consegue fazer POST para o webhook
    Simula o que a Evolution API deveria fazer quando uma mensagem chega
    """
    print(f"🧪 Testando se Evolution API pode alcançar o webhook...")
    print(f"   Evolution API: {EVO_URL}")
    print(f"   Webhook URL: {WEBHOOK_URL}")
    
    headers = {"apikey": EVO_TOKEN, "Content-Type": "application/json"}
    
    # Simular payload que a Evolution API enviaria
    test_payload = {
        "event": "MESSAGES_UPSERT",
        "instance": INSTANCE,
        "data": {
            "key": {
                "remoteJid": "5511999999999@s.whatsapp.net",
                "fromMe": False,
                "id": "TEST_MESSAGE_ID"
            },
            "message": {
                "conversation": "Teste de webhook - mensagem simulada"
            },
            "messageTimestamp": 1234567890
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Tentar fazer POST do Evolution para o Cloud Run
            print(f"\n📤 Fazendo POST para webhook...")
            resp = await client.post(
                WEBHOOK_URL,
                json=test_payload,
                headers={"User-Agent": "EvolutionAPI/1.0"},
                timeout=10.0
            )
            
            print(f"\n✅ Status: {resp.status_code}")
            print(f"📄 Response: {resp.text}")
            
            if resp.status_code == 200:
                print(f"\n🎉 WEBHOOK ESTÁ ACESSÍVEL DA INTERNET!")
                print(f"   O problema NÃO é firewall/rede")
                print(f"\n❌ O PROBLEMA É: Evolution API não está disparando o webhook")
                print(f"   Possíveis causas:")
                print(f"   1. Webhook configurado mas não ativado corretamente")
                print(f"   2. Bug na Evolution API")
                print(f"   3. Instância precisa ser reconectada")
            else:
                print(f"\n❌ Webhook retornou status inesperado: {resp.status_code}")
                
        except httpx.TimeoutException:
            print(f"\n❌ TIMEOUT: Webhook não respondeu")
            print(f"   Pode ser problema de rede/firewall")
        except httpx.ConnectError as e:
            print(f"\n❌ ERRO DE CONEXÃO: {e}")
            print(f"   Cloud Run pode estar inacessível")
        except Exception as e:
            print(f"\n❌ ERRO: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook_from_evolution())
