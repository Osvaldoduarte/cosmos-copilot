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

async def restart_instance():
    print(f"🔄 Reiniciando instância: {INSTANCE}")
    print(f"   Isso vai forçar reload do webhook...")
    
    headers = {"apikey": EVO_TOKEN}
    
    async with httpx.AsyncClient() as client:
        try:
            # Restart instance
            resp = await client.put(
                f"{EVO_URL}/instance/restart/{INSTANCE}",
                headers=headers
            )
            
            if resp.status_code in [200, 201]:
                print(f"\n✅ Instância reiniciada com sucesso!")
                print(f"   Aguarde 10 segundos para reconectar...")
                await asyncio.sleep(10)
                
                # Check status
                check_resp = await client.get(
                    f"{EVO_URL}/instance/connect/{INSTANCE}",
                    headers=headers
                )
                
                if check_resp.status_code == 200:
                    print(f"✅ Instância reconectada!")
                    print(f"\n📱 TESTE AGORA: Envie uma mensagem pelo WhatsApp")
                else:
                    print(f"⚠️  Status: {check_resp.status_code}")
                    print(f"   Pode precisar escanear QR code")
            else:
                print(f"\n❌ Erro ao re iniciar: {resp.status_code}")
                print(f"   Response: {resp.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")

if __name__ == "__main__":
    asyncio.run(restart_instance())
