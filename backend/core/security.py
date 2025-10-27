import bcrypt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto plano corresponde a um hash usando bcrypt.
    Retorna True se corresponder, False caso contrário.

    ✅ CORRIGIDO: Usando bcrypt nativo para evitar problemas de compatibilidade
    """
    try:
        # Trunca para 72 bytes (limite do bcrypt) e codifica
        plain_password_bytes = plain_password[:72].encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')

        # Compara usando bcrypt nativo
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except Exception as e:
        print(f"❌ Erro ao verificar senha: {e}")
        return False


def get_password_hash(password: str) -> str:
    """
    Cria um hash bcrypt a partir de uma senha em texto plano.

    ✅ CORRIGIDO: Usando bcrypt nativo
    """
    try:
        # Trunca para 72 bytes e codifica
        password_bytes = password[:72].encode('utf-8')

        # Gera o salt e cria o hash usando bcrypt nativo
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(password_bytes, salt)

        # Decodifica para string
        return hashed_bytes.decode('utf-8')
    except Exception as e:
        print(f"❌ Erro ao gerar hash: {e}")
        raise