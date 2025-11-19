# Em backend/core/security.py
# (SUBSTITUA O ARQUIVO INTEIRO)

import os
# 💡 Importante para segurança
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt

from core import database
from schemas import UserInDB, TokenData

# --- Configuração do JWT ---

# 1. Tenta pegar do ambiente (Cloud Run)
SECRET_KEY = os.getenv("SECRET_KEY")

# 2. Lógica de Segurança para Produção
if not SECRET_KEY:
    # Se não tiver chave definida, geramos uma aleatória na hora.
    # AVISO: Isso invalida todos os logins sempre que o servidor reinicia (deploy).
    # É seguro, mas pode ser chato para o usuário se o deploy for frequente.
    print("⚠️  [SECURITY] ATENÇÃO: SECRET_KEY não encontrada no .env. Gerando chave temporária e aleatória.")
    print("⚠️  [SECURITY] Para persistência de login entre deploys, configure a variável SECRET_KEY no Cloud Run.")
    SECRET_KEY = secrets.token_urlsafe(64)

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 dias

# --- Dependência OAuth2 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# --- Funções de Hash ---

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


# --- Funções de Lógica de Autenticação ---

def authenticate_user(username: str, password: str) -> Optional[UserInDB]:
    """
    Verifica se um usuário existe e se a senha está correta.
    """
    # print(f"--- [DEBUG Auth] Buscando: '{username}'") # 💡 Comentei logs excessivos para produção
    user_data = database.get_user(username)

    if not user_data:
        return None

    user = UserInDB(**user_data)
    if not verify_password(password, user.hashed_password):
        return None

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


# --- Funções de Dependência de Segurança ---

async def get_current_user(
        request: Request,  # 💡 Adicionado para ler query params
        token: Optional[str] = Depends(oauth2_scheme)
) -> UserInDB:
    # 1. Tenta pegar do Header (oauth2_scheme faz isso, mas pode falhar se vier vazio)
    # 2. Se falhar, tenta pegar da Query String (?token=...)
    if not token:
        token = request.query_params.get("token")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

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
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Usuário inativo")
    return current_user