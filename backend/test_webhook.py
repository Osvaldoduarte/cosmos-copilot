import httpx
import json

WEBHOOK_URL = "https://cosmos-backend-129644477821.us-central1.run.app/webhook/evolution"

# Simular payload da Evolution API
test_payload = {
    "event": "MESSAGES_UPSERT",
    "data": {
        "key": {
            "remoteJid": "5511999999999@s.whatsapp.net",
            "fromMe": False,
            "id": "TEST_MESSAGE_ID"
        },
        "message": {
            "conversation": "Teste de webhook"
        },
        "messageTimestamp": 1234567890
    }
}

print(f"🧪 Testando webhook endpoint: {WEBHOOK_URL}")
print(f"📦 Payload: {json.dumps(test_payload, indent=2)}")

try:
    response = httpx.post(
        WEBHOOK_URL,
        json=test_payload,
        timeout=10.0,
        headers={"User-Agent": "EvolutionAPI-Test"}
    )
    
    print(f"\n✅ Status: {response.status_code}")
    print(f"📄 Response: {response.text}")
    
    if response.status_code == 200:
        print("\n🎉 Webhook endpoint está FUNCIONANDO!")
    else:
        print(f"\n❌ Webhook retornou status {response.status_code}")
        
except httpx.TimeoutException:
    print("\n❌ TIMEOUT: Webhook não respondeu em 10 segundos")
except httpx.ConnectError as e:
    print(f"\n❌ ERRO DE CONEXÃO: {e}")
except Exception as e:
    print(f"\n❌ ERRO: {e}")
