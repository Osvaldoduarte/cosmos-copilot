import redis
import os
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    print("❌ REDIS_URL não encontrada no .env")
    exit()

try:
    # Conexão
    r = redis.from_url(REDIS_URL, decode_responses=True, ssl_cert_reqs=None)

    print("🧹 Iniciando limpeza CIRÚRGICA do Redis...")
    print("⏳ Isso pode levar alguns segundos dependendo da quantidade de chaves...")

    count = 0
    batch = []

    # Usa scan_iter para não estourar a memória (Pega um por um sem travar)
    # match="chat:*" garante que só apaga as conversas
    for key in r.scan_iter(match="chat:*", count=100):
        batch.append(key)

        # Quando juntar 100 chaves, deleta o lote
        if len(batch) >= 100:
            r.delete(*batch)
            count += 100
            print(f"🔥 {count} chaves removidas...", end="\r")
            batch = []  # Limpa o lote

    # Deleta o restante que sobrou (menos de 100)
    if batch:
        r.delete(*batch)
        count += len(batch)

    print(f"\n✅ Limpeza Concluída! Total removido: {count} conversas.")

except Exception as e:
    print(f"\n❌ Erro crítico: {e}")