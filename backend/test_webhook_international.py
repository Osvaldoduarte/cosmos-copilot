import requests
import json
import time

# Tenta descobrir a porta ou usa 8000
PORT = 8000
BASE_URL = f"http://localhost:{PORT}"

payload = {
  "event": "messages.upsert",
  "instance": "cosmos-wpp-osvaldo",
  "data": {
    "key": {
      "remoteJid": "12068996705@s.whatsapp.net",
      "fromMe": False,
      "id": f"TEST_MSG_{int(time.time())}"
    },
    "pushName": "Alana Teste Debug",
    "message": {
      "conversation": "Teste de recebimento forçado pelo Agente"
    },
    "messageTimestamp": int(time.time())
  }
}

try:
    print(f"Enviando webhook para {BASE_URL}/webhook/cosmos-wpp-osvaldo...")
    response = requests.post(f"{BASE_URL}/webhook/cosmos-wpp-osvaldo", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Erro ao conectar: {e}")
