from passlib.context import CryptContext

# Cria um contexto para o hashing, especificando que usaremos o algoritmo bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto plano corresponde a um hash.
    Retorna True se corresponder, False caso contrário.
    """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Cria um hash bcrypt a partir de uma senha em texto plano.
    """
    return pwd_context.hash(password)