# Importa a função de hashing do nosso módulo de segurança
from core.security import get_password_hash

# Defina as senhas em texto plano que você quer usar
senha_vendedor1 = "senha123"
senha_vendedor2 = "senha456" # Ou a senha real que você definiu para o vendedor2

# Gera os hashes usando a função do nosso projeto
hash_vendedor1 = get_password_hash(senha_vendedor1)
hash_vendedor2 = get_password_hash(senha_vendedor2)

# Imprime os hashes gerados para que você possa copiá-los
print("-" * 50)
print(f"Hash gerado para '{senha_vendedor1}':")
print(hash_vendedor1)
print("-" * 50)
print(f"\nHash gerado para '{senha_vendedor2}':")
print(hash_vendedor2)
print("-" * 50)
print("\nCopie e cole estes hashes no arquivo 'backend/core/database.py'")
print("-" * 50)