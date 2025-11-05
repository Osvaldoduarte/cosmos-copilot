# Em backend/core/security.py
# (SUBSTITUA o conteúdo deste arquivo)

import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt  # Usando bcrypt nativo como no seu arquivo original

from core import database
from schemas import UserInDB, TokenData  # Importando do novo schemas.py

# --- Configuração do JWT (Movido de main.py) ---
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

# --- Dependência OAuth2 (Movido de main.py) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Funções de Hash (Do seu arquivo original) ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se uma senha em texto plano corresponde a um hash usando bcrypt."""
    try:
        plain_password_bytes = plain_password[:72].encode('utf-8')
        hashed_password_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)
    except Exception as e:
        print(f"❌ Erro ao verificar senha: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Cria um hash bcrypt a partir de uma senha em texto plano."""
    try:
        password_bytes = password[:72].encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        hashed_bytes = bcrypt.hashpw(password_bytes, salt)
        return hashed_bytes.decode('utf-8')
    except Exception as e:
        print(f"❌ Erro ao gerar hash: {e}")
        raise


# --- Funções de Lógica de Autenticação (Movidas de main.py) ---

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """
    Verifica se um usuário existe e se a senha está correta.
    Retorna o objeto UserInDB se for bem-sucedido, None caso contrário.
    """
    print(f"--- [DEBUG authenticate_user] Iniciando verificação ---")
    print(f"Buscando usuário: '{username}'")
    user_data = database.get_user(username)  # Busca do DB (dicionário)

    if not user_data:
        print(f"[DEBUG authenticate_user] Usuário não encontrado.")
        return None

    print(f"[DEBUG authenticate_user] Usuário encontrado: {user_data['username']}")

    # Converte o dicionário do DB para o modelo Pydantic UserInDB
    user = UserInDB(**user_data)

    print(f"[DEBUG authenticate_user] Hash armazenado: '{user.hashed_password}'")
    print(f"[DEBUG authenticate_user] Verificando senha digitada ('{password}') contra o hash...")

    if not verify_password(password, user.hashed_password):
        print(f"[DEBUG authenticate_user] Verificação de senha: INCORRETA.")
        return None

    print(f"[DEBUG authenticate_user] Verificação de senha: CORRETA.")
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um novo token de acesso JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Funções de Dependência de Segurança (Movidas de main.py) ---

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    """
    Dependência FastAPI: Decodifica o token, valida e retorna o usuário.
    (Esta era a função que estava faltando no security.py)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_data = TokenData(username=username)

    except JWTError:
        raise credentials_exception

    user_data = database.get_user(token_data.username)
    if user_data is None:
        raise credentials_exception

    user = UserInDB(**user_data)
    return user


async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    """
    Dependência FastAPI: Pega o usuário atual e verifica se ele está ativo.
    (Esta era a função que estava faltando no security.py)
    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    return current_user