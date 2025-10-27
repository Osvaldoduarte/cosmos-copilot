"""
🧪 Script de Teste - VENAI Backend
Valida as correções antes do deploy
"""

import sys
import importlib.util

print("🧪 Iniciando validação das correções...\n")

# ==============================================================================
# TESTE 1: Validar NumPy
# ==============================================================================
print("1️⃣ Validando versão do NumPy...")
try:
    import numpy as np

    version = np.__version__
    major_version = int(version.split('.')[0])

    if major_version < 2:
        print(f"   ✅ NumPy {version} (compatível com ChromaDB)")
    else:
        print(f"   ❌ NumPy {version} - INCOMPATÍVEL!")
        print("   Execute: pip install numpy==1.26.4")
        sys.exit(1)
except ImportError:
    print("   ❌ NumPy não instalado!")
    sys.exit(1)

# ==============================================================================
# TESTE 2: Validar bcrypt
# ==============================================================================
print("\n2️⃣ Validando bcrypt nativo...")
try:
    import bcrypt

    # Teste rápido de hash e verificação
    test_password = "teste123"
    test_bytes = test_password[:72].encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    test_hash = bcrypt.hashpw(test_bytes, salt)

    # Verifica se a validação funciona
    is_valid = bcrypt.checkpw(test_bytes, test_hash)

    if is_valid:
        print(f"   ✅ bcrypt funcionando corretamente")
        print(f"   Hash de teste gerado: {test_hash[:30].decode('utf-8')}...")
    else:
        print("   ❌ bcrypt não está validando corretamente!")
        sys.exit(1)

except ImportError:
    print("   ❌ bcrypt não instalado!")
    sys.exit(1)
except Exception as e:
    print(f"   ❌ Erro ao testar bcrypt: {e}")
    sys.exit(1)

# ==============================================================================
# TESTE 3: Validar ChromaDB
# ==============================================================================
print("\n3️⃣ Validando ChromaDB...")
try:
    import chromadb

    print(f"   ✅ ChromaDB {chromadb.__version__} importado com sucesso")
except ImportError as e:
    print(f"   ❌ Erro ao importar ChromaDB: {e}")
    print("   Execute: pip install chromadb==0.4.24")
    sys.exit(1)

# ==============================================================================
# TESTE 4: Validar security.py
# ==============================================================================
print("\n4️⃣ Validando security.py...")
try:
    # Tenta importar o módulo core.security
    spec = importlib.util.spec_from_file_location("security", "./core/security.py")
    if spec and spec.loader:
        security = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(security)

        # Testa as funções
        test_pwd = "senha123"
        test_hash = security.get_password_hash(test_pwd)

        print(f"   ✅ get_password_hash() funcionando")
        print(f"   Hash gerado: {test_hash[:30]}...")

        # Testa verificação
        is_correct = security.verify_password(test_pwd, test_hash)
        is_wrong = security.verify_password("senhaErrada", test_hash)

        if is_correct and not is_wrong:
            print(f"   ✅ verify_password() funcionando corretamente")
        else:
            print(f"   ❌ verify_password() não está funcionando!")
            sys.exit(1)

    else:
        print("   ❌ Não foi possível carregar security.py")
        sys.exit(1)

except FileNotFoundError:
    print("   ⚠️ security.py não encontrado (talvez você não esteja no diretório correto)")
except Exception as e:
    print(f"   ❌ Erro ao validar security.py: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# ==============================================================================
# TESTE 5: Validar dependências essenciais
# ==============================================================================
print("\n5️⃣ Validando dependências essenciais...")
required_packages = {
    "fastapi": "0.118.0",
    "httpx": "0.28.1",
    "langchain": "0.3.27",
    "jose": None,  # python-jose
}

all_ok = True
for package, expected_version in required_packages.items():
    try:
        if package == "jose":
            import jose

            print(f"   ✅ python-jose instalado")
        else:
            mod = __import__(package)
            version = getattr(mod, '__version__', 'desconhecida')
            print(f"   ✅ {package} {version}")
    except ImportError:
        print(f"   ❌ {package} NÃO instalado!")
        all_ok = False

if not all_ok:
    print("\n   Execute: pip install -r requirements-backend.txt")
    sys.exit(1)

# ==============================================================================
# TESTE 6: Gerar hashes para database.py
# ==============================================================================
print("\n6️⃣ Gerando novos hashes para database.py...")
try:
    import bcrypt

    senhas = {
        "vendedor1": "senha123",
        "vendedor2": "senha456"
    }

    print("\n   📋 Cole estes hashes no seu database.py:")
    print("   " + "=" * 60)

    for user, pwd in senhas.items():
        pwd_bytes = pwd[:72].encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        hash_final = bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

        print(f'''
    "{user}": {{
        "username": "{user}",
        "hashed_password": "{hash_final}",
        ...
    }},''')

    print("   " + "=" * 60)

except Exception as e:
    print(f"   ⚠️ Não foi possível gerar hashes: {e}")

# ==============================================================================
# RESUMO
# ==============================================================================
print("\n" + "=" * 70)
print("✅ TODAS AS VALIDAÇÕES PASSARAM!")
print("=" * 70)
