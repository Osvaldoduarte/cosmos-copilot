#!/usr/bin/env python3
"""
LIMPEZA TOTAL - LGPD
Remove TUDO: Memória + Redis + mostra como limpar frontend
"""
import redis
import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print(" 🔒 LIMPEZA TOTAL LGPD - TODAS AS FONTES")
print("=" * 70)
print()

# 1. REDIS
print("1️⃣ LIMPANDO REDIS...")
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
print(f"   Conectando: {redis_url[:30]}...")

try:
    r = redis.from_url(redis_url, decode_responses=True)
    keys = list(r.scan_iter(match="chat:*", count=10000))
    
    if keys:
        print(f"   Encontradas: {len(keys)} conversas")
        for key in keys:
            r.delete(key)
        print(f"   ✅ {len(keys)} conversas DELETADAS do Redis")
    else:
        print("   ✅ Redis já está vazio")
except Exception as e:
    print(f"   ❌ Erro: {e}")

print()

# 2. BACKEND (memória será limpa ao reiniciar)
print("2️⃣ BACKEND (memória)")
print("   ⚠️  Você DEVE reiniciar o backend:")
print("      Ctrl+C no terminal do backend")
print("      uvicorn main:app --reload")

print()

# 3. FRONTEND
print("3️⃣ FRONTEND (cache do navegador)")
print("   ⚠️  Abra DevTools (F12) e:")
print("      1. Aba 'Application'")
print("      2. 'Local Storage' > localhost:3000 > 'Clear All'")
print("      3. 'Session Storage' > 'Clear All'")
print("      4. FECHE E REABRA o navegador")

print()
print("=" * 70)
print(" ✅ REDIS LIMPO! Siga os próximos passos acima.")
print("=" * 70)
