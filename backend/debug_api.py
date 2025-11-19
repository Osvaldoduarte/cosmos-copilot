import os
import json
import httpx
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load env
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")

async def main():
    url = f"{EVO_URL}/chat/findMessages/{EVO_INSTANCE}"
    headers = {"apikey": EVO_TOKEN}
    # Target the specific conversation
    jid = "554192235407@s.whatsapp.net"
    payload = {"where": {"key": {"remoteJid": jid}}, "limit": 10, "page": 1}
    
    print(f"Querying {url} for {jid}...")
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            msgs = data.get("messages", {}).get("records", [])
            print(f"Found {len(msgs)} messages.")
            for m in msgs:
                key = m.get("key", {})
                from_me = key.get("fromMe")
                # Only interested in client messages (fromMe=False) or if list is empty
                if not from_me:
                    print("\n--- CLIENT MESSAGE ---")
                    print(json.dumps(m, indent=2))
        else:
            print(f"Error: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    asyncio.run(main())
