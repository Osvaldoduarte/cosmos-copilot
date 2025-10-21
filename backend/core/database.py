from typing import Dict, Optional

# Simulação do nosso banco de dados de usuários.
# No futuro, isso pode ser substituído por uma consulta a um banco de dados real.

# Hashes gerados para as senhas "senha123" e "senha456" usando a função get_password_hash.
# É importante que você nunca saiba a senha original, apenas o hash.
users_db: Dict[str, Dict] = {
    "vendedor1": {
        "username": "vendedor1",
        "full_name": "João Silva",
        "hashed_password": "$2b$12$HORoqPvMQc/vN/NxDQ8d/uTfhqgPgZ/X1dmNkuLTkIUTk2A.xZvq2", # Hash para "senha123"
        "disabled": False,
        "tenant_id": "cosmoserp"
    },
    "vendedor2": {
        "username": "vendedor2",
        "full_name": "Maria Souza",
        "hashed_password": "$2b$12$3P7jZNBp6vxWTBqZXUIsEeiTnqdQYq4zMo0Z4wnzlbmE4mjYzFoBW", # Hash para "senha456" (exemplo)
        "disabled": False,
        "tenant_id": "cosmoserp"
    }
}

def get_user(username: str) -> Optional[Dict]:
    """Busca um usuário no nosso 'banco de dados'."""
    if username in users_db:
        return users_db[username]
    return None