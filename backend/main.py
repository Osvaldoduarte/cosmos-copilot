import os, time, httpx, uuid, json, uvicorn, asyncio, copy, redis, traceback
from pathlib import Path
from dotenv import load_dotenv

# --- Carregamento de Variáveis (ANTES de importar core modules) ---
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from sqlalchemy import not_
from fastapi.concurrency import run_in_threadpool

# Seus módulos internos (DEPOIS do load_dotenv)
from core import security, database, cerebro_ia


# --- Cores para Logs ---
class Colors:
    RED = '\033[91m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    END = '\033[0m'


def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")


def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")


def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")


def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


# --- Carregamento de Variáveis ---
EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 dias

REDIS_URL = os.getenv("REDIS_URL")
redis_client = None
if REDIS_URL:
    try:
        # ssl_cert_reqs=None ajuda na compatibilidade com algumas versões de linux/container
        redis_client = redis.from_url(REDIS_URL, decode_responses=True, ssl_cert_reqs=None)
        print(f"{Colors.GREEN}✅ Conectado ao Redis (Upstash)!{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Falha no Redis: {e}{Colors.END}")
else:
    print(f"{Colors.YELLOW}⚠️  REDIS_URL não encontrada. Rodando apenas em memória.{Colors.END}")

# --- Estado Global ---
STATE_LOCK = asyncio.Lock()
CONVERSATION_STATE_STORE: Dict[str, Any] = {}

def save_to_redis(jid: str):
    """Salva uma conversa específica da memória para o Redis"""
    if not redis_client or jid not in CONVERSATION_STATE_STORE: return
    try:
        data = CONVERSATION_STATE_STORE[jid]
        # Salva com validade de 7 dias para não encher o banco free
        redis_client.setex(f"chat:{jid}", timedelta(days=7), json.dumps(data))
    except Exception as e:
        print_error(f"Erro ao salvar no Redis: {e}")

def load_redis_cache():
    """Carrega tudo do Redis para a memória ao iniciar"""
    if not redis_client: return
    try:
        keys = redis_client.keys("chat:*")
        count = 0
        for key in keys:
            jid = key.split("chat:")[1]
            data_json = redis_client.get(key)
            if data_json:
                CONVERSATION_STATE_STORE[jid] = json.loads(data_json)
                count += 1
        print_success(f"📂 Cache recuperado do Redis: {count} conversas.")
    except Exception as e:
        print_error(f"Erro ao carregar cache Redis: {e}")

# --- Modelos Pydantic ---
class NewConversationRequest(BaseModel):
    recipient_number: str
    initial_message: str


class MessageSendRequest(BaseModel):
    conversation_id: str
    message_text: str


class InstanceCreateRequest(BaseModel):
    instanceName: Optional[str] = None


class TenantInfo(BaseModel):
    id: str
    name: str
    instance_name: Optional[str] = None
    type: str = "CLIENT"
    instance_token: Optional[str] = None

    class Config:
        from_attributes = True

# 2. Modelo do Usuário atualizado
class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    tenant_id: str
    # 👇 AQUI ESTÁ A CORREÇÃO: Adicionamos o campo tenant
    tenant: Optional[TenantInfo] = None

    class Config:
        from_attributes = True


class AIQueryRequest(BaseModel):
    conversation_id: str
    query: Optional[str] = None
    type: str = "analysis"  # analysis | internal

class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: str
    company_id: str # Identificador único da empresa (slug)
    company_name: str # Nome legível da empresa

class CreateUserSchema(BaseModel):
    username: str
    password: str
    full_name: str


# --- Configuração do FastAPI ---
app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ===================================================================
# 1. SEGURANÇA
# ===================================================================

def authenticate_user(username: str, password: str) -> Optional[User]:
    print(f"🔍 Tentando autenticar usuário: '{username}'")

    # 1. Usa a nova função que já traz o Tenant junto
    user_db = database.get_user_with_tenant(username)

    if not user_db:
        print(f"❌ Usuário '{username}' não encontrado no Banco de Dados!")
        return None

    print(f"✅ Usuário encontrado.")

    # 2. Verifica a senha
    if not security.verify_password(password, user_db.hashed_password):
        print(f"❌ Senha incorreta para '{username}'")
        return None

    print(f"🎉 Senha correta! Login autorizado.")

    # 3. Converte o objeto do SQLAlchemy para o modelo Pydantic
    # Precisamos extrair os dados manualmente ou usar from_orm se configurado
    user_dict = {
        "username": user_db.username,
        "full_name": user_db.full_name,
        "hashed_password": user_db.hashed_password,
        "disabled": user_db.disabled,
        "tenant_id": user_db.tenant_id,
        # Adicione o objeto tenant se seu modelo User esperar
        "tenant": user_db.tenant
    }

    return User(**user_dict)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_active_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_db = database.get_user_with_tenant(username)
    if user_db is None: raise credentials_exception

    # Converte para Pydantic
    user_dict = {
        "username": user_db.username,
        "full_name": user_db.full_name,
        "hashed_password": user_db.hashed_password,
        "disabled": user_db.disabled,
        "tenant_id": user_db.tenant_id,
        "tenant": user_db.tenant
    }

    return User(**user_dict)



def verify_super_admin(current_user: User = Depends(get_current_active_user)):
    if current_user.tenant_id != "admin_master":
        raise HTTPException(status_code=403, detail="Acesso restrito ao Super Admin.")
    return current_user

# ===================================================================
# 2. LÓGICA DE NEGÓCIO
# ===================================================================
def find_existing_conversation_jid(jid: str) -> str | None:
    if jid in CONVERSATION_STATE_STORE: return jid
    number_part = jid.split('@')[0]
    if number_part.startswith('55') and len(number_part) > 4:
        ddi, ddd, rest = number_part[:2], number_part[2:4], number_part[4:]
        alt_jid = None
        if len(rest) == 9 and rest.startswith('9'):
            alt_jid = f"{ddi}{ddd}{rest[1:]}@s.whatsapp.net"
        elif len(rest) == 8:
            alt_jid = f"{ddi}{ddd}9{rest}@s.whatsapp.net"
        if alt_jid and alt_jid in CONVERSATION_STATE_STORE:
            return alt_jid
    return None


async def send_whatsapp_message(recipient_jid: str, message_text: str, user: User) -> bool:
    if not user.tenant or not user.tenant.instance_name:
        print_error("Usuário sem instância vinculada")
        return False

    instance_name = user.tenant.instance_name
    api_token = user.tenant.instance_token or EVO_TOKEN  # Use tenant's token or fallback

    number_only = recipient_jid.split('@')[0]
    url = f"{EVO_URL}/message/sendText/{instance_name}"
    headers = {'Content-Type': 'application/json', 'apikey': api_token}
    payload = {"number": number_only, "text": message_text}
    
    print_info(f"📤 Enviando mensagem para {number_only} via instância {instance_name}")
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code in [200, 201]:
                print_success(f"✅ Mensagem enviada com sucesso para {number_only}")
                return True
            else:
                print_error(f"❌ Evolution API retornou status {resp.status_code}: {resp.text}")
                return False
    except Exception as e:
        print_error(f"❌ Falha ao enviar mensagem: {e}")
        traceback.print_exc()
    return False


# --- Gerenciador de Conexões WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print_error(f"Erro no broadcast WS: {e}")

manager = ConnectionManager()


async def create_evolution_instance(instance_name: str):
    """Cria uma instância nova na Evolution API"""
    url = f"{EVO_URL}/instance/create"
    headers = {"apikey": EVO_TOKEN}
    payload = {
        "instanceName": instance_name,
        "token": "",
        "qrcode": False,
        "integration": "WHATSAPP-BAILEYS"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)

            # Debug: Mostra o que a Evolution respondeu
            print_info(f"Evolution Create Resp: {resp.status_code} - {resp.text}")

            if resp.status_code == 201:
                return resp.json()  # Sucesso: Retorna Dict
            elif resp.status_code == 403 and "already exists" in resp.text:
                # Se já existe, tentamos buscar os dados dela para não travar
                print_warning("Instância já existe, tentando recuperar dados...")
                fetch_resp = await client.get(f"{EVO_URL}/instance/fetchInstances", headers=headers)
                if fetch_resp.status_code == 200:
                    instances = fetch_resp.json()
                    # Procura a instância na lista
                    found = next((i for i in instances if i['instance']['instanceName'] == instance_name), None)
                    return found  # Retorna Dict ou None

            return None  # Falha

    except Exception as e:
        print_error(f"Falha crítica ao criar instância: {e}")
        return None

@app.get("/manager/dashboard")
async def get_dashboard_data(current_user: User = Depends(get_current_active_user)):
    # Validação extra para não quebrar se o tenant vier vazio
    if not current_user.tenant:
        raise HTTPException(status_code=400, detail="Usuário sem empresa vinculada.")

    instance_status = "DESCONECTADO"

    # 1. Buscar status na Evolution API
    if current_user.tenant.instance_name:
        try:
            # Usa o nome da instância da empresa
            url = f"{EVO_URL}/instance/connectionState/{current_user.tenant.instance_name}"
            headers = {"apikey": EVO_TOKEN}
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    state_data = resp.json()
                    # Tenta pegar de vários lugares dependendo da versão da API
                    state = state_data.get("instance", {}).get("state") or state_data.get("state")
                    instance_status = state or "DESCONECTADO"
        except Exception as e:
            print(f"Erro ao buscar status evolution: {e}")
            instance_status = "ERRO_API"

    # 2. Buscar usuários da mesma empresa
    db = database.SessionLocal()
    try:
        company_users = db.query(database.UserDB).filter(
            database.UserDB.tenant_id == current_user.tenant_id
        ).all()

        users_list = [
            {"username": u.username, "full_name": u.full_name, "disabled": u.disabled}
            for u in company_users
        ]
    finally:
        db.close()

    return {
        "company_name": current_user.tenant.name,
        "instance_name": current_user.tenant.instance_name,
        "connection_status": instance_status,
        "users": users_list
    }


@app.post("/manager/add_user")
async def add_user_to_company(req: CreateUserSchema, current_user: User = Depends(get_current_active_user)):
    """
    Adiciona um novo vendedor à empresa do gerente logado.
    """
    db = database.SessionLocal()

    # Verifica se usuário já existe (globalmente ou na empresa)
    existing = db.query(database.UserDB).filter(database.UserDB.username == req.username).first()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Nome de usuário já existe.")

    try:
        new_user = database.UserDB(
            username=req.username,
            full_name=req.full_name,
            hashed_password=security.get_password_hash(req.password),
            tenant_id=current_user.tenant_id,  # <--- VINCULA À MESMA EMPRESA DO GERENTE
            disabled=False
        )
        db.add(new_user)
        db.commit()
    except Exception as e:
        db.rollback()
        db.close()
        print(f"Erro ao criar user: {e}")
        raise HTTPException(status_code=500, detail="Erro ao salvar usuário")

    db.close()
    return {"status": "success", "message": f"Usuário {req.username} criado com sucesso!"}


class UpdateUserSchema(BaseModel):
    full_name: Optional[str] = None
    password: Optional[str] = None
    # Username geralmente não se muda fácil pois é a chave primária,
    # mas se quiser mudar, precisaria de uma lógica mais complexa de banco.
    # Por enquanto vamos permitir mudar Nome e Senha.

class UpdateTenantSchema(BaseModel):
    name: Optional[str] = None
    instance_token: Optional[str] = None
    # Adicione outros campos se necessário

class AdminAddUserSchema(BaseModel):
    username: str
    password: str
    full_name: str


class ImportChatsRequest(BaseModel):
    jids: List[str]


@app.get("/evolution/chats/summary")
async def list_available_chats(
        page: int = 1,
        limit: int = 10,
        search: str = "",
        current_user: User = Depends(get_current_active_user)
):
    """
    Lista contatos para importação com FILTRO RIGOROSO.
    Apenas números reais (@s.whatsapp.net).
    Suporta busca por nome ou número.
    """
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")

    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    headers = {"apikey": api_token}

    all_items = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # TENTATIVA 1: CHATS (Mantemos caso o banco da Evo volte a funcionar um dia)
        try:
            url_chats = f"{EVO_URL}/chat/findChats/{instance_name}"
            resp = await client.post(url_chats, headers=headers, json={})

            if resp.status_code == 200:
                raw_chats = resp.json()
                if isinstance(raw_chats, dict): raw_chats = raw_chats.get('records') or []

                for chat in raw_chats:
                    jid = chat.get("id") or chat.get("remoteJid")

                    # --- FILTRO ANTI-GRUPO E ANTI-LIXO ---
                    if not jid or not str(jid).endswith("@s.whatsapp.net"):
                        continue  # Pula se for grupo ou lixo

                    # Filtro de Arquivadas (se disponível no endpoint de chats)
                    if chat.get("archive") or chat.get("isArchived"):
                        continue

                    all_items.append({
                        "id": jid,
                        "name": chat.get("name") or chat.get("pushName") or jid.split('@')[0],
                        "picture": chat.get("profilePictureUrl") or "",
                        "unread": chat.get("unreadCount", 0),
                        "subtitle": jid.split('@')[0]
                    })
            else:
                raise Exception("Force Fallback")

        except Exception:
            # TENTATIVA 2: CONTATOS (Onde estamos operando agora)
            print_info("🔄 Fallback: Buscando e FILTRANDO contatos...")
            try:
                url_contacts = f"{EVO_URL}/chat/findContacts/{instance_name}"
                resp_c = await client.post(url_contacts, headers=headers, json={})

                if resp_c.status_code == 200:
                    payload = resp_c.json()
                    contacts_list = []

                    if isinstance(payload, list):
                        contacts_list = payload
                    elif isinstance(payload, dict):
                        contacts_list = payload.get('contacts') or payload.get('records') or []

                    for contact in contacts_list:
                        # Pega o ID
                        raw_id = contact.get("id")
                        remote_jid = contact.get("remoteJid")
                        final_jid = remote_jid or raw_id

                        # --- FILTRO RIGOROSO ---
                        # 1. Deve existir
                        # 2. Deve ser string
                        # 3. DEVE terminar com @s.whatsapp.net (Pessoas apenas)
                        if not final_jid or not isinstance(final_jid, str):
                            continue

                        if not final_jid.endswith("@s.whatsapp.net"):
                            continue  # Tchau grupos, tchau cmia..., tchau broadcast!

                        # Nome Bonito
                        name = (
                                contact.get("pushName") or
                                contact.get("name") or
                                contact.get("verifiedName") or
                                contact.get("notify")
                        )
                        if not name: name = final_jid.split('@')[0]

                        all_items.append({
                            "id": final_jid,
                            "name": name,
                            "picture": contact.get("profilePictureUrl") or "",
                            "unread": 0,
                            "subtitle": final_jid.split('@')[0]
                        })

                    # Ordena alfabeticamente para facilitar
                    all_items.sort(key=lambda x: x['name'].lower() if x['name'] else "")

                    print_success(f"✅ Filtrados e Recuperados: {len(all_items)} contatos reais.")
                else:
                    print_error(f"❌ Erro Contatos: {resp_c.status_code}")
            except Exception as e_cont:
                print_error(f"Erro crítico no fallback: {e_cont}")

    # Filtro de busca (se fornecido)
    if search and search.strip():
        search_lower = search.strip().lower()
        print_info(f"🔍 Filtrando por: '{search}'")
        all_items = [
            item for item in all_items
            if search_lower in item["name"].lower() or search_lower in item["id"].lower()
        ]
        print_info(f"📊 {len(all_items)} resultados encontrados")

    # Paginação
    total = len(all_items)
    start = (page - 1) * limit
    end = start + limit
    paged_items = all_items[start:end]

    return {
        "data": paged_items,
        "total": total,
        "page": page,
        "has_more": end < total
    }


@app.post("/evolution/chats/import")
async def import_selected_chats(
        req: ImportChatsRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_active_user)
):
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Erro de Tenant")

    print_info(f"📥 Iniciando importação OTIMIZADA de {len(req.jids)} conversas...")

    async def run_import_task(jids_to_import):
        instance_name = current_user.tenant.instance_name
        api_token = current_user.tenant.instance_token or EVO_TOKEN
        headers = {"apikey": api_token}

        async with httpx.AsyncClient(timeout=30.0) as client:
            for jid in jids_to_import:
                # Verifica se é JID válido de pessoa
                if "@g.us" in jid or "@broadcast" in jid: continue

                processed_msgs = []
                chat_name = jid.split('@')[0]
                avatar = ""

                try:
                    # 1. Tenta buscar mensagens (Limite 20 para economizar banda)
                    payload = {
                        "where": {"key": {"remoteJid": jid}},
                        "limit": 20,
                        "page": 1
                    }
                    resp = await client.post(
                        f"{EVO_URL}/chat/findMessages/{instance_name}",
                        headers=headers, json=payload
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        messages_data = data.get("messages", {}).get("records", [])

                        if not messages_data:
                            print_warning(f"   ⚠️ {jid}: Sem mensagens. Ignorando salvamento.")
                            continue  # <--- PULA SE NÃO TIVER MENSAGENS (ECONOMIA REDIS)

                        for m in messages_data:
                            if m.get("pushName"): chat_name = m.get("pushName")

                            msg_content = m.get("message", {})
                            content = (
                                    msg_content.get("conversation") or
                                    msg_content.get("extendedTextMessage", {}).get("text") or
                                    msg_content.get("imageMessage", {}).get("caption")
                            )

                            if not content:
                                if "imageMessage" in msg_content:
                                    content = "📷 [Imagem]"
                                elif "audioMessage" in msg_content:
                                    content = "🎤 [Áudio]"
                                else:
                                    content = "📝 [Mensagem]"

                            if content:
                                processed_msgs.append({
                                    "content": content,
                                    "sender": "vendedor" if m.get("key", {}).get("fromMe") else "cliente",
                                    "timestamp": m.get("messageTimestamp") or int(time.time()),
                                    "message_id": m.get("key", {}).get("id")
                                })

                        processed_msgs.sort(key=lambda x: x["timestamp"])

                    else:
                        # Se a API falhar (Erro 500), NÃO IMPORTAMOS NADA.
                        # Melhor não ter a conversa do que ter lixo vazio consumindo banco.
                        print_error(f"   ❌ Erro API Evolution ({resp.status_code}) para {jid}. Pulando.")
                        continue

                    # 2. Tenta buscar Foto (Opcional, falha silenciosa)
                    try:
                        pic_resp = await client.post(
                            f"{EVO_URL}/chat/fetchProfilePictureUrl/{instance_name}",
                            headers=headers, json={"number": jid}
                        )
                        if pic_resp.status_code == 200:
                            avatar = pic_resp.json().get("profilePictureUrl", "")
                    except:
                        pass

                    # 3. SÓ SALVA SE TIVER CONTEÚDO REAL
                    if processed_msgs:
                        async with STATE_LOCK:
                            CONVERSATION_STATE_STORE[jid] = {
                                "name": chat_name,
                                "avatar_url": avatar,
                                "messages": processed_msgs,
                                "unread": False,
                                "lastUpdated": processed_msgs[-1]["timestamp"] * 1000
                            }

                        # Salva no Redis (ÚNICO PONTO DE ESCRITA)
                        save_to_redis(jid)
                        print_success(f"   💾 {chat_name}: Salvo com {len(processed_msgs)} msgs.")

                except Exception as exc:
                    print_error(f"   ❌ Erro processando {jid}: {exc}")

    background_tasks.add_task(run_import_task, req.jids)
    return {"status": "import_started"}

# ===================================================================
# ROTAS DE ADMINISTRAÇÃO AVANÇADA (CRUD TOTAL)
# ===================================================================

@app.delete("/admin/users/{username}")
async def admin_delete_user(username: str, admin: User = Depends(verify_super_admin)):
    """
    Rota exclusiva para o Admin deletar QUALQUER usuário de QUALQUER empresa.
    """
    if username == admin.username:
        raise HTTPException(status_code=400, detail="Você não pode se auto-deletar por aqui.")

    db = database.SessionLocal()
    user_to_delete = db.query(database.UserDB).filter(database.UserDB.username == username).first()

    if not user_to_delete:
        db.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    try:
        db.delete(user_to_delete)
        db.commit()
        return {"status": "success", "message": f"Usuário {username} removido do sistema."}
    except Exception as e:
        db.rollback()
        print_error(f"Erro ao deletar user admin: {e}")
        raise HTTPException(status_code=500, detail="Erro ao deletar usuário")
    finally:
        db.close()

@app.put("/admin/tenants/{tenant_id}")
async def update_tenant(tenant_id: str, req: UpdateTenantSchema, admin: User = Depends(verify_super_admin)):
    """Edita dados de uma empresa"""
    db = database.SessionLocal()
    tenant = db.query(database.TenantDB).filter(database.TenantDB.id == tenant_id).first()

    if not tenant:
        db.close()
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    try:
        if req.name:
            tenant.name = req.name
        if req.instance_token:
            tenant.instance_token = req.instance_token

        db.commit()
        return {"status": "success", "message": "Empresa atualizada"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.delete("/admin/tenants/{tenant_id}")
async def delete_tenant(tenant_id: str, admin: User = Depends(verify_super_admin)):
    """
    DELETA UMA EMPRESA E TODOS OS SEUS USUÁRIOS.
    Cuidado: Ação destrutiva.
    """
    if tenant_id == "admin_master":
        raise HTTPException(status_code=400, detail="Não é possível deletar a conta Master.")

    db = database.SessionLocal()
    tenant = db.query(database.TenantDB).filter(database.TenantDB.id == tenant_id).first()

    if not tenant:
        db.close()
        raise HTTPException(status_code=404, detail="Empresa não encontrada")

    try:
        # 1. Opcional: Deslogar/Deletar instância na Evolution
        if tenant.instance_name:
            try:
                # Tenta deletar na Evolution para liberar recurso (Fire & Forget)
                url = f"{EVO_URL}/instance/delete/{tenant.instance_name}"
                headers = {"apikey": EVO_TOKEN}
                async with httpx.AsyncClient() as client:
                    await client.delete(url, headers=headers)
            except Exception as e:
                print_error(f"Erro ao deletar instância Evolution: {e}")

        # 2. Deletar Usuários da Empresa
        db.query(database.UserDB).filter(database.UserDB.tenant_id == tenant_id).delete()

        # 3. Deletar a Empresa
        db.delete(tenant)

        db.commit()
        return {"status": "success", "message": f"Empresa {tenant_id} e seus usuários foram removidos."}
    except Exception as e:
        db.rollback()
        print_error(f"Erro ao deletar tenant: {e}")
        raise HTTPException(status_code=500, detail="Erro ao excluir empresa.")
    finally:
        db.close()


@app.get("/admin/tenants/{tenant_id}/users")
async def get_tenant_users(tenant_id: str, admin: User = Depends(verify_super_admin)):
    """Lista usuários de uma empresa específica"""
    db = database.SessionLocal()
    try:
        users = db.query(database.UserDB).filter(database.UserDB.tenant_id == tenant_id).all()
        return [
            {"username": u.username, "full_name": u.full_name, "disabled": u.disabled}
            for u in users
        ]
    finally:
        db.close()


@app.post("/admin/tenants/{tenant_id}/users")
async def add_user_to_tenant_admin(
        tenant_id: str,
        req: AdminAddUserSchema,
        admin: User = Depends(verify_super_admin)
):
    """Adiciona usuário a uma empresa específica (pelo Admin)"""
    db = database.SessionLocal()

    # Verifica duplicidade
    if db.query(database.UserDB).filter(database.UserDB.username == req.username).first():
        db.close()
        raise HTTPException(status_code=400, detail="Usuário já existe.")

    try:
        new_user = database.UserDB(
            username=req.username,
            full_name=req.full_name,
            hashed_password=security.get_password_hash(req.password),
            tenant_id=tenant_id,
            disabled=False
        )
        db.add(new_user)
        db.commit()
        return {"status": "success", "message": "Usuário criado"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.get("/users/me")
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.put("/manager/users/{username}")
async def update_user_company(
        username: str,
        req: UpdateUserSchema,
        current_user: User = Depends(get_current_active_user)
):
    """Edita um usuário da MESMA empresa do gerente"""
    db = database.SessionLocal()

    # Busca o usuário garantindo que ele pertença à empresa do gerente
    user_to_edit = db.query(database.UserDB).filter(
        database.UserDB.username == username,
        database.UserDB.tenant_id == current_user.tenant_id
    ).first()

    if not user_to_edit:
        db.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado nesta empresa.")

    try:
        if req.full_name:
            user_to_edit.full_name = req.full_name
        if req.password and len(req.password) > 0:
            user_to_edit.hashed_password = security.get_password_hash(req.password)

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro ao editar: {e}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar usuário")
    finally:
        db.close()

    return {"status": "success", "message": "Usuário atualizado"}


@app.delete("/manager/users/{username}")
async def delete_user_company(username: str, current_user: User = Depends(get_current_active_user)):
    """Remove um usuário da equipe"""
    if username == current_user.username:
        raise HTTPException(status_code=400, detail="Você não pode se deletar!")

    db = database.SessionLocal()
    user_to_delete = db.query(database.UserDB).filter(
        database.UserDB.username == username,
        database.UserDB.tenant_id == current_user.tenant_id
    ).first()

    if not user_to_delete:
        db.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    try:
        db.delete(user_to_delete)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Erro ao deletar: {e}")
        raise HTTPException(status_code=500, detail="Erro ao deletar usuário")
    finally:
        db.close()

    return {"status": "success", "message": "Usuário removido"}

@app.post("/admin/register_user")
async def register_user(req: UserCreateRequest, current_user: User = Depends(get_current_active_user)):
    # 1. Verifica se o Tenant (Empresa) já existe
    db = database.SessionLocal()
    tenant = db.query(database.TenantDB).filter(database.TenantDB.id == req.company_id).first()

    instance_name = f"cosmos-{req.company_id}"  # Padrão de nome

    if not tenant:
        print_info(f"🏢 Criando nova empresa e instância: {req.company_name}")

        # 2. Cria instância na Evolution
        evo_data = await create_evolution_instance(instance_name)
        if not evo_data:
            raise HTTPException(status_code=500, detail="Falha ao criar instância no WhatsApp")

        # 3. Salva Tenant no Banco
        tenant_data = {
            "id": req.company_id,
            "name": req.company_name,
            "instance_name": instance_name,
            "instance_id": evo_data.get("instance", {}).get("instanceId"),
            "instance_token": evo_data.get("hash", {}).get("apikey")
        }
    else:
        print_info(f"🏢 Empresa {req.company_name} já existe. Adicionando usuário.")
        tenant_data = None  # Não precisa recriar

    # 4. Prepara Usuário
    user_data = {
        "username": req.username,
        "full_name": req.full_name,
        "hashed_password": security.get_password_hash(req.password),
        "tenant_id": req.company_id
    }

    # 5. Salva tudo (Se tenant_data for None, a função trata)
    if tenant_data:
        success = database.create_tenant_and_user(tenant_data, user_data)
    else:
        # Só cria o usuário
        try:
            new_user = database.UserDB(**user_data)
            db.add(new_user)
            db.commit()
            success = True
        except:
            success = False

    db.close()

    if success:
        return {"status": "created", "instance": instance_name}
    else:
        raise HTTPException(status_code=500, detail="Erro ao salvar no banco")

async def process_and_broadcast_message(conversation_id: str, message_obj: Dict[str, Any]):
    global CONVERSATION_STATE_STORE
    try:
        async with STATE_LOCK:
            # Garante JID formatado
            if "@" not in conversation_id and conversation_id.isdigit():
                conversation_id = f"{conversation_id}@s.whatsapp.net"

            if conversation_id not in CONVERSATION_STATE_STORE:
                CONVERSATION_STATE_STORE[conversation_id] = {
                    "name": conversation_id.split('@')[0], "messages": [],
                    "unread": False, "unreadCount": 0, "lastUpdated": 0, "avatar_url": ""
                }

            CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)
            CONVERSATION_STATE_STORE[conversation_id]["lastUpdated"] = message_obj.get("timestamp",
                                                                                       int(time.time())) * 1000
            if message_obj.get("sender") == "cliente":
                CONVERSATION_STATE_STORE[conversation_id]["unread"] = True
                CONVERSATION_STATE_STORE[conversation_id]["unreadCount"] = CONVERSATION_STATE_STORE[
                                                                               conversation_id].get("unreadCount",
                                                                                                    0) + 1

        save_to_redis(conversation_id)

        # Broadcast via WebSocket
        await manager.broadcast({
            "type": "new_message",
            "conversation_id": conversation_id,
            "message": message_obj,
            "name": CONVERSATION_STATE_STORE[conversation_id].get("name"),
            "avatar_url": CONVERSATION_STATE_STORE[conversation_id].get("avatar_url"),
            "unreadCount": CONVERSATION_STATE_STORE[conversation_id].get("unreadCount", 0)
        })

    except Exception as e:
        print_error(f"Erro processando mensagem: {e}")


async def sync_tenant_history(instance_name: str, api_token: str, tenant_id: str):
    """Sincroniza histórico de uma empresa específica sob demanda"""
    print_info(f"🔄 Sincronizando histórico para empresa: {tenant_id} (Instância: {instance_name})")

    url = f"{EVO_URL}/chat/findMessages/{instance_name}"  # Usa o nome da instância do cliente
    headers = {"apikey": api_token}

    async with STATE_LOCK:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {"apikey": EVO_TOKEN}

                # 1. Busca Mensagens (Aumentei o limite para pegar mais contexto)
                # Vamos usar as mensagens para descobrir nomes que não estão na lista de contatos
                msgs_resp = await client.post(f"{EVO_URL}/chat/findMessages/{EVO_INSTANCE}", headers=headers,
                                              json={"limit": 500, "page": 1})
                messages_data = msgs_resp.json().get("messages", {}).get("records",
                                                                         []) if msgs_resp.status_code == 200 else []

                print_info(f"📥 Carregadas {len(messages_data)} mensagens da Evolution API")

                # Mapa auxiliar: JID -> Nome Descoberto nas Mensagens (PushName)
                discovered_names = {}

                # Processa mensagens primeiro para extrair nomes
                messages_by_jid = {}

                for m in messages_data:
                    key = m.get("key", {})
                    # 🔧 FIX: Usa remoteJidAlt se disponível (WhatsApp Business)
                    remote_jid_original = key.get("remoteJid")
                    remote_jid_alt = key.get("remoteJidAlt")
                    remote_jid = remote_jid_alt or remote_jid_original

                    # Debug: mostra quando há diferença
                    if remote_jid_original and remote_jid_alt and remote_jid_original != remote_jid_alt:
                        print_info(f"🔄 Convertendo {remote_jid_original} → {remote_jid_alt}")

                    if not remote_jid: continue

                    # Tenta capturar o nome do perfil (pushName)
                    if m.get("pushName"):
                        discovered_names[remote_jid] = m.get("pushName")

                    if remote_jid not in messages_by_jid:
                        messages_by_jid[remote_jid] = []

                    # Extração Robusta de Conteúdo
                    msg_content = m.get("message", {})
                    content = (
                            msg_content.get("conversation") or
                            msg_content.get("extendedTextMessage", {}).get("text") or
                            msg_content.get("imageMessage", {}).get("caption")
                    )

                    # Fallbacks para mídia sem legenda
                    if not content:
                        if "imageMessage" in msg_content:
                            content = "📷 [Imagem]"
                        elif "audioMessage" in msg_content:
                            content = "🎤 [Áudio]"
                        elif "videoMessage" in msg_content:
                            content = "🎥 [Vídeo]"
                        elif "documentMessage" in msg_content:
                            content = "📄 [Documento]"
                        elif "stickerMessage" in msg_content:
                            content = "👾 [Figurinha]"

                    if content:
                        messages_by_jid[remote_jid].append({
                            "content": content,
                            "sender": "vendedor" if key.get("fromMe") else "cliente",
                            "timestamp": m.get("messageTimestamp"),
                            "message_id": key.get("id")
                        })

                # 2. Busca Contatos
                contacts_resp = await client.post(f"{EVO_URL}/chat/findContacts/{EVO_INSTANCE}", headers=headers,
                                                  json={})
                contacts = contacts_resp.json() if contacts_resp.status_code == 200 else []

                # 3. Monta o Estado Final
                # Adiciona contatos da lista oficial
                for contact in contacts:
                    jid = contact.get("remoteJid")
                    if not jid or "@g.us" in jid: continue  # Ignora grupos

                    # Decide o nome: Nome salvo > PushName descoberto > Número
                    official_name = contact.get("name") or contact.get("pushName")
                    final_name = official_name or discovered_names.get(jid) or jid.split('@')[0]

                    # Formata se for número puro (Ex: 5541...)
                    if final_name.isdigit() and len(final_name) > 10:
                        final_name = f"+{final_name}"

                    processed_msgs = messages_by_jid.get(jid, [])
                    processed_msgs.sort(key=lambda x: x["timestamp"])

                    CONVERSATION_STATE_STORE[jid] = {
                        "name": final_name,
                        "avatar_url": contact.get("profilePicUrl") or "",
                        "messages": processed_msgs,
                        "unread": False,
                        "unreadCount": 0,
                        "lastUpdated": int(time.time()) * 1000
                    }

                # Adiciona conversas que existem nas mensagens mas não na lista de contatos
                for jid, msgs in messages_by_jid.items():
                    if jid not in CONVERSATION_STATE_STORE and "@g.us" not in jid:
                        final_name = discovered_names.get(jid) or jid.split('@')[0]
                        msgs.sort(key=lambda x: x["timestamp"])
                        CONVERSATION_STATE_STORE[jid] = {
                            "name": final_name,
                            "avatar_url": "",  # Não temos foto aqui fácil
                            "messages": msgs,
                            "unread": False,
                            "unreadCount": 0,
                            "lastUpdated": msgs[-1]["timestamp"] * 1000 if msgs else 0
                        }


                print_success(f"✅ Sincronização Concluída! {len(CONVERSATION_STATE_STORE)} conversas carregadas.")

                if redis_client:
                    print_info("💾 Salvando sincronização no Redis...")
                    for jid in CONVERSATION_STATE_STORE:
                        save_to_redis(jid)

                # Log detalhado de cada conversa
                for jid, data in CONVERSATION_STATE_STORE.items():
                    msg_count = len(data.get("messages", []))
                    name = data.get("name", "Sem nome")
                    print_info(f"   📱 {name} ({jid}): {msg_count} mensagens")
        except Exception as e:
            print_error(f"Erro na sincronização: {e}")


# ===================================================================
# 3. ROTAS (ENDPOINTS)
# ===================================================================

@app.on_event("startup")
async def startup_event():

    # --- INICIALIZAÇÃO IA ---
    print_info("🧠 Inicializando Cérebro IA...")
    try:
        client = cerebro_ia.initialize_chroma_client()
        llm, retriever, embed, playbook = cerebro_ia.load_models(client)
        from core.shared import IA_MODELS
        IA_MODELS["llm"] = llm
        IA_MODELS["retriever"] = retriever
        IA_MODELS["embeddings"] = embed
        print_success("🧠 Cérebro IA Carregado!")
    except Exception as e:
        print_error(f"Falha ao carregar IA: {e}")


# --- Auth ---
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    print(
        f"📨 Recebida requisição de login. Username: {form_data.username}, Password: {form_data.password}")  # <--- NOVO
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        print("🚫 Login negado (401)")  # <--- NOVO
        raise HTTPException(status_code=401, detail="Login incorreto")
    token = create_access_token(data={"sub": user.username, "tenant_id": user.tenant_id})
    return {"access_token": token, "token_type": "bearer"}


# --- WebSocket ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# --- Instância ---
@app.get("/evolution/instance/status")
async def get_instance_status(current_user: User = Depends(get_current_active_user)):
    url = f"{EVO_URL}/instance/connectionState/{EVO_INSTANCE}"
    headers = {"apikey": EVO_TOKEN}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return {"instance": {"state": "close", "notFound": True}}
    except Exception:
        pass
    return {"instance": {"state": "close"}}


# --- Download de Mídia ---
@app.post("/evolution/media/download")
async def download_media(
    request: dict,
    current_user: User = Depends(get_current_active_user)
):
    """
    Baixa mídia da Evolution API e retorna em base64.
    Payload esperado: { "message": { ... } }
    """
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    
    try:
        url = f"{EVO_URL}/chat/getBase64FromMediaMessage/{instance_name}"
        headers = {"apikey": api_token, "Content-Type": "application/json"}
        
        # print_info(f"📥 Baixando mídia da Evolution API para instância {instance_name}...")
        # print_info(f"📦 Payload (resumo): {str(request)[:200]}...") # Descomente se necessário
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=request)
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                if data and "base64" in data:
                    # print_success(f"✅ Mídia baixada com sucesso")
                    return data
                else:
                    print_warning(f"⚠️ Evolution retornou {resp.status_code} mas sem 'base64': {data}")
                    return data # Retorna mesmo assim para debug
            else:
                print_error(f"❌ Evolution retornou status {resp.status_code}: {resp.text}")
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Erro ao baixar mídia: {resp.text}"
                )
    
    except httpx.TimeoutException:
        print_error("❌ Timeout ao baixar mídia")
        raise HTTPException(status_code=504, detail="Timeout ao baixar mídia")
    except Exception as e:
        print_error(f"❌ Erro ao baixar mídia: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao baixar mídia: {str(e)}")


@app.post("/evolution/instance/create_and_get_qr")
async def create_and_get_qr(request: InstanceCreateRequest = None,
                            current_user: User = Depends(get_current_active_user)):
    # Valida se o usuário tem empresa vinculada
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Usuário sem empresa vinculada.")

    instance_name = current_user.tenant.instance_name
    api_key = current_user.tenant.instance_token or EVO_TOKEN  # Usa token do tenant ou fallback

    print_info(f"🔌 Buscando QR Code para: {instance_name}")

    headers = {"apikey": api_key}

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            # 1. Tenta PEGAR o QR Code direto (Rota /instance/connect)
            # Essa rota retorna o QR se a instância existe e está desconectada
            connect_url = f"{EVO_URL}/instance/connect/{instance_name}"
            resp = await client.get(connect_url, headers=headers)

            if resp.status_code == 200:
                return resp.json()  # Sucesso! Retorna o QR

            # 2. Se der 404 (Não encontrada), tenta CRIAR
            if resp.status_code == 404:
                print_warning(f"Instância {instance_name} não encontrada. Tentando recriar...")
                create_url = f"{EVO_URL}/instance/create"
                payload = {
                    "instanceName": instance_name,
                    "token": "",
                    "qrcode": True,  # Já pede o QR na criação
                    "integration": "WHATSAPP-BAILEYS"
                }
                create_resp = await client.post(create_url, headers=headers, json=payload)

                if create_resp.status_code == 201:
                    # Se criou, já devolve o QR que vem na resposta de criação
                    return create_resp.json()
                else:
                    # Se falhar a criação
                    print_error(f"Falha ao recriar: {create_resp.text}")
                    raise HTTPException(status_code=502, detail="Erro ao criar instância na Evolution.")

            # Se der outro erro (Ex: 400 se já estiver conectada)
            error_detail = resp.json() if resp.content else {"error": resp.text}

            # Se já estiver conectada, retorna um status fake para o frontend entender
            if "already connected" in str(error_detail).lower():
                return {"instance": {"state": "open"}}

            print_error(f"Erro Evolution: {resp.status_code} - {resp.text}")
            raise HTTPException(status_code=resp.status_code, detail=f"Erro Evolution: {resp.text}")

        except httpx.ConnectError as e:
            print_error(f"Erro Conexão: {e}")
            raise HTTPException(status_code=504, detail="Timeout na Evolution API")


@app.delete("/evolution/instance/logout")
async def logout_instance(current_user: User = Depends(get_current_active_user)):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{EVO_URL}/instance/logout/{EVO_INSTANCE}", headers={"apikey": EVO_TOKEN})
    return {"status": "logged_out"}


# --- Chat ---
@app.get("/conversations")
async def get_all_conversations(
        current_user: User = Depends(get_current_active_user)
):
    if not current_user.tenant or not current_user.tenant.instance_name:
        return {"status": "error", "conversations": []}

    formatted = []
    seen_jids = set()

    if redis_client:
        try:
            pattern = "chat:*"
            for key in redis_client.scan_iter(match=pattern, count=100):
                try:
                    if "@" not in key and len(key.split(":")) < 2: continue

                    data_json = redis_client.get(key)
                    if data_json:
                        data = json.loads(data_json)
                        parts = key.split("chat:")
                        if len(parts) > 1:
                            jid = parts[1]
                        else:
                            continue

                        if "@g.us" in jid: continue
                        if "status@broadcast" in jid: continue

                        # Pega a última mensagem (se houver)
                        last_msg = ""
                        messages = data.get("messages", [])
                        if messages:
                            last_msg = messages[-1]["content"]

                        # --- REMOVIDO O FILTRO DE MENSAGENS VAZIAS ---
                        # if not messages: continue  <-- ESTA LINHA ESTAVA MATANDO SUA LISTA

                        formatted.append({
                            "id": jid,
                            "name": data.get("name", jid.split('@')[0]),
                            "avatar_url": data.get("avatar_url", ""),
                            "lastMessage": last_msg,
                            "unread": data.get("unread", False),
                            "unreadCount": data.get("unreadCount", 0),
                            "lastUpdated": data.get("lastUpdated", 0)
                        })
                        seen_jids.add(jid)
                except Exception:
                    continue
        except Exception as e:
            print_error(f"Erro Redis Scan: {e}")

    # Ordena pela data
    formatted.sort(key=lambda x: x["lastUpdated"], reverse=True)

    return {"status": "success", "conversations": formatted}

# 🟢 ROTA INTELIGENTE DE MENSAGENS (COM SUPORTE A MÍDIA E BUSCA SOB DEMANDA)
@app.get("/conversations/{jid:path}/messages")
async def get_conversation_messages(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Busca mensagens tentando forçar a leitura do histórico antigo do WhatsApp.
    """
    print_info(f"📨 [API] Requisição de mensagens para: {jid}")
    
    # 1. Tratamento do JID
    if "@" not in jid and jid.isdigit():
        target_jid = f"{jid}@s.whatsapp.net"
    else:
        target_jid = jid

    real_jid = find_existing_conversation_jid(target_jid) or target_jid
    print_info(f"📨 [API] JID normalizado: {real_jid}")

    # 2. Verifica Memória (Cache)
    stored_msgs = []
    if real_jid in CONVERSATION_STATE_STORE:
        stored_msgs = CONVERSATION_STATE_STORE[real_jid].get("messages", [])
        print_info(f"📨 [API] Encontrado em memória: {len(stored_msgs)} mensagens")
    else:
        print_warning(f"⚠️ [API] JID {real_jid} NÃO encontrado em CONVERSATION_STATE_STORE")
        print_info(f"📊 [API] JIDs disponíveis em memória: {list(CONVERSATION_STATE_STORE.keys())[:5]}")

    # 2.5 Verifica Redis (Se memória falhou ou tem pouco)
    if (not stored_msgs or len(stored_msgs) < 20) and redis_client:
        try:
            print_info(f"🔍 Buscando no Redis para: {real_jid}")
            cached_data = redis_client.get(f"chat:{real_jid}")
            if cached_data:
                data = json.loads(cached_data)
                redis_msgs = data.get("messages", [])
                
                if len(redis_msgs) > len(stored_msgs):
                    stored_msgs = redis_msgs
                    # Popula memória para próximas vezes
                    async with STATE_LOCK:
                        CONVERSATION_STATE_STORE[real_jid] = data
                    print_success(f"✅ [API] Recuperado do Redis: {len(stored_msgs)} mensagens")
        except Exception as e:
            print_error(f"Erro ao ler do Redis: {e}")

    # Se já temos um bom número de mensagens (ex: > 20), retornamos o cache para ser rápido
    if len(stored_msgs) > 20:
        print_success(f"✅ [API] Retornando {len(stored_msgs)} mensagens do cache")
        return stored_msgs

    # 3. Se vazio ou pouco, busca na API
    print_info(f"🔍 Buscando histórico PROFUNDO para: {real_jid}")
    try:
        # Usa a instância do usuário se disponível, senão fallback para global
        instance_name = EVO_INSTANCE
        api_token = EVO_TOKEN
        
        if current_user.tenant and current_user.tenant.instance_name:
            instance_name = current_user.tenant.instance_name
            api_token = current_user.tenant.instance_token or EVO_TOKEN
            
        url = f"{EVO_URL}/chat/findMessages/{instance_name}"
        headers = {"apikey": api_token}

        # Payload Agressivo: Pede muito, sem filtro de data
        payload = {
            "where": {
                "key": {"remoteJid": real_jid}
            },
            "limit": 200,  # Tenta pegar 200 por vez
            "page": 1
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)

            messages_data = []
            if resp.status_code == 200:
                data = resp.json()
                messages_data = data.get("messages", {}).get("records", [])
                print_info(f"📥 [API] Evolution retornou {len(messages_data)} mensagens")
            else:
                print_error(f"❌ [API] Evolution retornou status {resp.status_code}")

            # Se ainda vier vazio, é possível que o histórico não tenha baixado na VM.
            # Nesse caso, não há muito o que fazer via API além de esperar a sincronização nativa.

            processed_msgs = []
            for m in messages_data:
                msg_content = m.get("message", {})
                content = (
                        msg_content.get("conversation") or
                        msg_content.get("extendedTextMessage", {}).get("text") or
                        msg_content.get("imageMessage", {}).get("caption")
                )
                
                # Extrai URLs de mídia
                media_url = None
                media_type = None
                
                if not content:
                    if "imageMessage" in msg_content:
                        content = "📷 [Imagem]"
                        media_type = "image"
                        media_url = msg_content.get("imageMessage", {}).get("url")
                    elif "audioMessage" in msg_content:
                        content = "🎤 [Áudio]"
                        media_type = "audio"
                        media_url = msg_content.get("audioMessage", {}).get("url")
                    elif "videoMessage" in msg_content:
                        content = "🎥 [Vídeo]"
                        media_type = "video"
                        media_url = msg_content.get("videoMessage", {}).get("url")
                    elif "documentMessage" in msg_content:
                        content = "📄 [Documento]"
                        media_type = "document"
                        media_url = msg_content.get("documentMessage", {}).get("url")
                    elif "stickerMessage" in msg_content:
                        content = "👾 [Figurinha]"
                        media_type = "sticker"
                        media_url = msg_content.get("stickerMessage", {}).get("url")
                else:
                    # Verifica se tem imagem mesmo com caption
                    if "imageMessage" in msg_content:
                        media_type = "image"
                        media_url = msg_content.get("imageMessage", {}).get("url")

                if content:
                    msg_obj = {
                        "content": content,
                        "sender": "vendedor" if m.get("key", {}).get("fromMe") else "cliente",
                        "timestamp": m.get("messageTimestamp"),
                        "message_id": m.get("key", {}).get("id"),
                        "raw_message": m  # <--- Necessário para baixar mídia
                    }
                    
                    # Adiciona mídia se existir (mesmo sem URL, para tentar baixar via raw_message)
                    if media_type:
                        msg_obj["media"] = {
                            "type": media_type,
                            "url": media_url
                        }
                    
                    processed_msgs.append(msg_obj)

            # Remove duplicatas (pelo ID) e ordena
            seen_ids = set()
            unique_msgs = []
            # Junta com o que já tinha na memória
            all_potential_msgs = stored_msgs + processed_msgs

            for msg in all_potential_msgs:
                if msg['message_id'] not in seen_ids:
                    unique_msgs.append(msg)
                    seen_ids.add(msg['message_id'])

            unique_msgs.sort(key=lambda x: x["timestamp"])

            # Salva na memória
            async with STATE_LOCK:
                if real_jid not in CONVERSATION_STATE_STORE:
                    CONVERSATION_STATE_STORE[real_jid] = {"messages": [], "name": real_jid.split('@')[0],
                                                          "unread": False}
                CONVERSATION_STATE_STORE[real_jid]["messages"] = unique_msgs

            print_success(f"✅ [API] Retornando {len(unique_msgs)} mensagens (cache + API)")
            return unique_msgs

    except Exception as e:
        print_error(f"Erro ao buscar histórico: {e}")
        traceback.print_exc()

    print_warning(f"⚠️ [API] Retornando {len(stored_msgs)} mensagens (fallback)")
    return stored_msgs

@app.get("/contacts/info/{number}")
async def get_contact_info_route(number: str, current_user: User = Depends(get_current_active_user)):
    jid = f"{number}@s.whatsapp.net" if "@" not in number else number
    if jid in CONVERSATION_STATE_STORE:
        data = CONVERSATION_STATE_STORE[jid]
        return {"name": data["name"], "avatar_url": data.get("avatar_url", "")}
    return {"name": number, "avatar_url": ""}


@app.post("/messages/send")
async def send_message(request: MessageSendRequest, background_tasks: BackgroundTasks,
                       current_user: User = Depends(get_current_active_user)):
    # Pass current_user to send_whatsapp_message
    success = await send_whatsapp_message(request.conversation_id, request.message_text, current_user)
    if not success: 
        print_error(f"❌ Falha ao enviar mensagem para {request.conversation_id}")
        raise HTTPException(status_code=500, detail="Erro no envio")

    msg_obj = {
        "content": request.message_text, "sender": "vendedor",
        "timestamp": int(time.time()), "message_id": f"sent_{int(time.time())}"
    }
    background_tasks.add_task(process_and_broadcast_message, request.conversation_id, msg_obj)
    return {"status": "success"}


@app.post("/conversations/start_new")
async def start_new_conversation(request: NewConversationRequest, background_tasks: BackgroundTasks,
                                 current_user: User = Depends(get_current_active_user)):
    # Formata o número para JID
    number = request.recipient_number
    if "@" not in number:
        jid = f"{number}@s.whatsapp.net"
    else:
        jid = number

    # Envia a mensagem inicial - PASS current_user
    success = await send_whatsapp_message(jid, request.initial_message, current_user)
    if not success: raise HTTPException(status_code=500, detail="Falha ao enviar mensagem inicial")

    # Registra a mensagem e a conversa
    msg_obj = {
        "content": request.initial_message, "sender": "vendedor",
        "timestamp": int(time.time()), "message_id": f"sent_{int(time.time())}"
    }

    # Garante que a conversa exista no estado local
    async with STATE_LOCK:
        if jid not in CONVERSATION_STATE_STORE:
             CONVERSATION_STATE_STORE[jid] = {
                "name": request.recipient_number,
                "messages": [],
                "unread": False,
                "unreadCount": 0,
                "lastUpdated": int(time.time()) * 1000,
                "avatar_url": ""
            }

    background_tasks.add_task(process_and_broadcast_message, jid, msg_obj)
    return {"status": "success", "conversation_id": jid}


class ReactionRequest(BaseModel):
    conversation_id: str
    message_id: str
    emoji: str  # Pode ser vazio para remover reação


@app.post("/messages/react")
async def send_reaction(request: ReactionRequest, current_user: User = Depends(get_current_active_user)):
    """
    Envia uma reação emoji para uma mensagem específica.
    """
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    
    try:
        # Extrai o número do JID
        number = request.conversation_id.split('@')[0]
        
        # 🔧 NOVO: Determina fromMe baseado na mensagem alvo
        from_me = False
        if request.conversation_id in CONVERSATION_STATE_STORE:
            messages = CONVERSATION_STATE_STORE[request.conversation_id].get("messages", [])
            target_msg = next((m for m in messages if m.get("message_id") == request.message_id), None)
            if target_msg:
                # fromMe=True se a mensagem original foi enviada pelo vendedor
                from_me = (target_msg.get("sender") == "vendedor")
        
        # Monta a requisição para a Evolution API
        url = f"{EVO_URL}/message/sendReaction/{instance_name}"
        headers = {'Content-Type': 'application/json', 'apikey': api_token}
        payload = {
            "number": number,
            "options": {
                "key": {
                    "id": request.message_id,
                    "remoteJid": request.conversation_id,
                    "fromMe": from_me  # 👈 Agora dinâmico!
                },
                "reaction": request.emoji  # Vazio remove a reação
            }
        }
        
        print_info(f"👍 Enviando reação '{request.emoji}' para mensagem {request.message_id} (fromMe={from_me})")
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            
            if resp.status_code in [200, 201]:
                print_success(f"✅ Reação enviada com sucesso")
                
                # Atualiza localmente a mensagem com a reação
                async with STATE_LOCK:
                    if request.conversation_id in CONVERSATION_STATE_STORE:
                        messages = CONVERSATION_STATE_STORE[request.conversation_id].get("messages", [])
                        for msg in messages:
                            if msg.get("message_id") == request.message_id:
                                if "reactions" not in msg:
                                    msg["reactions"] = []
                                
                                # Remove reação anterior do vendedor
                                msg["reactions"] = [r for r in msg["reactions"] if r.get("from") != "vendedor"]
                                
                                # Adiciona nova reação (se não for vazia)
                                if request.emoji:
                                    msg["reactions"].append({
                                        "emoji": request.emoji,
                                        "from": "vendedor"
                                    })
                                
                                save_to_redis(request.conversation_id)
                                break
                
                # Broadcasta via WebSocket
                await manager.broadcast({
                    "type": "message_reaction",
                    "conversation_id": request.conversation_id,
                    "message_id": request.message_id,
                    "reaction": request.emoji,
                    "from": "vendedor"
                })
                
                return {"status": "success"}
            else:
                print_error(f"❌ Evolution API retornou status {resp.status_code}: {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=f"Erro ao enviar reação: {resp.text}")
        
    except Exception as e:
        print_error(f"❌ Falha ao enviar reação: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao enviar reação: {str(e)}")


# ============================================================================
# CONTACT PROFILE MANAGEMENT
# ============================================================================

class CustomNameRequest(BaseModel):
    custom_name: str  # Empty string to clear


@app.post("/contacts/{jid}/custom-name")
async def update_custom_name(jid: str, request: CustomNameRequest, current_user: User = Depends(get_current_active_user)):
    """
    Atualiza o nome customizado de um contato.
    Nome customizado tem prioridade sobre nome do WhatsApp.
    """
    if "@" not in jid:
        jid = f"{jid}@s.whatsapp.net"
    
    custom_name = request.custom_name.strip()
    
    async with STATE_LOCK:
        if jid not in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[jid] = {
                "messages": [],
                "unread": False,
                "unreadCount": 0,
                "lastUpdated": int(time.time()) * 1000
            }
        
        # Atualiza ou remove custom_name
        if custom_name:
            CONVERSATION_STATE_STORE[jid]["custom_name"] = custom_name
            print_success(f"✏️ Nome customizado definido para {jid}: {custom_name}")
        else:
            CONVERSATION_STATE_STORE[jid].pop("custom_name", None)
            print_info(f"🗑️ Nome customizado removido para {jid}")
        
        save_to_redis(jid)
    
    # Broadcasta atualização via WebSocket
    await manager.broadcast({
        "type": "profile_updated",
        "conversation_id": jid,
        "custom_name": custom_name if custom_name else None,
        "whatsapp_name": CONVERSATION_STATE_STORE[jid].get("whatsapp_name"),
        "avatar_url": CONVERSATION_STATE_STORE[jid].get("avatar_url")
    })
    
    return {"status": "success", "custom_name": custom_name if custom_name else None}


@app.get("/contacts/{jid}/refresh-profile")
async def refresh_profile(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Busca perfil atualizado do WhatsApp (foto e nome).
    """
    if "@" not in jid:
        jid = f"{jid}@s.whatsapp.net"
    
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    number = jid.split('@')[0]
    
    print_info(f"🔄 Atualizando perfil do WhatsApp para {number}")
    
    try:
        # Busca foto de perfil
        pic_url = f"{EVO_URL}/chat/fetchProfilePictureUrl/{instance_name}"
        headers = {'apikey': api_token, 'Content-Type': 'application/json'}
        payload = {"number": number}
        
        whatsapp_name = None
        avatar_url = None
        
        async with httpx.AsyncClient() as client:
            # Foto de perfil
            try:
                resp = await client.post(pic_url, headers=headers, json=payload, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    avatar_url = data.get("profilePictureUrl") or data.get("picture")
                    print_success(f"✅ Foto de perfil obtida para {number}")
            except Exception as e:
                print_warning(f"⚠️ Erro ao buscar foto: {e}")
            
            # Nome do WhatsApp (via fetchProfile)
            try:
                profile_url = f"{EVO_URL}/chat/fetchProfile/{instance_name}"
                resp = await client.post(profile_url, headers=headers, json=payload, timeout=10.0)
                if resp.status_code == 200:
                    data = resp.json()
                    whatsapp_name = data.get("pushName") or data.get("name")
                    print_success(f"✅ Nome do WhatsApp obtido para {number}: {whatsapp_name}")
            except Exception as e:
                print_warning(f"⚠️ Erro ao buscar nome: {e}")
        
        # Atualiza no estado
        async with STATE_LOCK:
            if jid not in CONVERSATION_STATE_STORE:
                CONVERSATION_STATE_STORE[jid] = {
                    "messages": [],
                    "unread": False,
                    "unreadCount": 0,
                    "lastUpdated": int(time.time()) * 1000
                }
            
            if whatsapp_name:
                CONVERSATION_STATE_STORE[jid]["whatsapp_name"] = whatsapp_name
            if avatar_url:
                CONVERSATION_STATE_STORE[jid]["avatar_url"] = avatar_url
            
            CONVERSATION_STATE_STORE[jid]["last_profile_check"] = int(time.time())
            
            save_to_redis(jid)
        
        # Broadcasta atualização
        await manager.broadcast({
            "type": "profile_updated",
            "conversation_id": jid,
            "custom_name": CONVERSATION_STATE_STORE[jid].get("custom_name"),
            "whatsapp_name": whatsapp_name,
            "avatar_url": avatar_url
        })
        
        return {
            "status": "success",
            "whatsapp_name": whatsapp_name,
            "avatar_url": avatar_url,
            "last_profile_check": CONVERSATION_STATE_STORE[jid]["last_profile_check"]
        }
        
    except Exception as e:
        print_error(f"❌ Erro ao atualizar perfil: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar perfil: {str(e)}")


@app.post("/ai/generate_suggestion")
async def generate_ai_suggestion(request: AIQueryRequest, current_user: User = Depends(get_current_active_user)):
    print_info(f"🤖 [API] Requisição de sugestão IA recebida - Conversa: {request.conversation_id}, Tipo: {request.type}")
    
    # Verifica se a IA foi inicializada
    from core.shared import IA_MODELS
    if not IA_MODELS.get("llm"):
        print_error("❌ [API] IA não inicializada - LLM não disponível")
        raise HTTPException(
            status_code=503, 
            detail="IA não inicializada. Verifique as configurações do Chroma e Gemini API no backend."
        )
    
    copilot = cerebro_ia.get_sales_copilot()
    if not copilot:
        print_error("❌ [API] Falha ao obter instância do SalesCopilot")
        raise HTTPException(
            status_code=503, 
            detail="Serviço de IA temporariamente indisponível."
        )

    # Get conversation history
    jid = request.conversation_id
    if "@" not in jid and jid.isdigit(): jid = f"{jid}@s.whatsapp.net"

    history = []
    if jid in CONVERSATION_STATE_STORE:
        history = CONVERSATION_STATE_STORE[jid].get("messages", [])
        print_info(f"📚 [API] Histórico encontrado: {len(history)} mensagens")
    else:
        print_warning(f"⚠️ [API] Nenhum histórico encontrado para {jid}")

    # Determine query
    user_query = request.query
    if not user_query and history:
        # Use last message from client if no query provided
        last_msg = next((m for m in reversed(history) if m["sender"] == "cliente"), None)
        if last_msg: 
            user_query = last_msg["content"]
            print_info(f"💬 [API] Usando última mensagem do cliente: '{user_query[:50]}...'")

    if not user_query:
        print_warning("⚠️ [API] Nenhuma query fornecida e sem mensagens do cliente")
        return {"status": "error", "message": "Nenhuma mensagem para analisar"}

    try:
        print_info(f"🧠 [API] Gerando sugestão para query: '{user_query[:100]}...'")
        result = copilot.generate_sales_suggestions(
            query=user_query,
            full_conversation_history=history,
            current_stage_id="unknown",
            is_private_query=(request.type == "internal"),
            client_data={}
        )
        print_success(f"✅ [API] Sugestão gerada com sucesso")
        return result
    except Exception as e:
        print_error(f"❌ [API] Erro ao gerar sugestão: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao processar IA: {str(e)}")


@app.post("/webhook/evolution")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        # print_info(f"🔍 Webhook Payload Completo: {json.dumps(body, indent=2)}")
        event = body.get("event")
        data = body.get("data")
        if not data: return {"status": "no_data"}

        if event == "messages.upsert":
            msg_data = data.get("message") or {}
            key = data.get("key") or {}

            # 🎭 Processar Reações
            if "reactionMessage" in msg_data:
                reaction_data = msg_data["reactionMessage"]
                target_msg_id = reaction_data.get("key", {}).get("id")
                emoji = reaction_data.get("text", "")
                jid = key.get("remoteJidAlt") or key.get("remoteJid")
                from_me = key.get("fromMe", False)
                
                if target_msg_id and jid:
                    who = "vendedor" if from_me else "cliente"
                    print_info(f"👍 Webhook: Reação '{emoji}' de {who} na mensagem {target_msg_id}")
                    
                    # Atualiza a mensagem com a reação
                    async with STATE_LOCK:
                        if jid in CONVERSATION_STATE_STORE:
                            messages = CONVERSATION_STATE_STORE[jid].get("messages", [])
                            for msg in messages:
                                if msg.get("message_id") == target_msg_id:
                                    if "reactions" not in msg:
                                        msg["reactions"] = []
                                    
                                    # Remove reação anterior da mesma pessoa
                                    msg["reactions"] = [r for r in msg["reactions"] if r.get("from") != who]
                                    
                                    # Adiciona nova reação (se não for vazia)
                                    if emoji:
                                        msg["reactions"].append({
                                            "emoji": emoji,
                                            "from": who
                                        })
                                        print_success(f"✅ Reação adicionada à mensagem {target_msg_id}")
                                    
                                    # Salva no Redis
                                    save_to_redis(jid)
                                    
                                    # Broadcasta atualização via WebSocket
                                    await manager.broadcast({
                                        "type": "message_reaction",
                                        "conversation_id": jid,
                                        "message_id": target_msg_id,
                                        "reaction": emoji,
                                        "from": who
                                    })
                                    break
                
                return {"status": "ok"}

            # Ignora mensagens enviadas por mim
            if not key.get("fromMe"):
                # 🔧 FIX: WhatsApp Business usa @lid (Local ID) temporário
                # Precisamos usar remoteJidAlt que contém o número real
                jid = key.get("remoteJidAlt") or key.get("remoteJid")

                # Extração Robusta de Conteúdo (Igual ao load_history)
                content = (
                    msg_data.get("conversation") or
                    msg_data.get("extendedTextMessage", {}).get("text") or
                    msg_data.get("imageMessage", {}).get("caption")
                )

                # Fallbacks para mídia sem legenda
                if not content:
                    if "imageMessage" in msg_data:
                        content = "📷 [Imagem]"
                    elif "audioMessage" in msg_data:
                        content = "🎤 [Áudio]"
                    elif "videoMessage" in msg_data:
                        content = "🎥 [Vídeo]"
                    elif "documentMessage" in msg_data:
                        content = "📄 [Documento]"
                    elif "stickerMessage" in msg_data:
                        content = "👾 [Figurinha]"

                if jid and content:
                    # Usa timestamp da mensagem se disponível
                    ts = data.get("messageTimestamp") or int(time.time())

                    msg_obj = {
                        "content": content,
                        "sender": "cliente",
                        "timestamp": ts,
                        "message_id": key.get("id")
                    }

                    print_info(f"📩 Webhook: Mensagem recebida de {jid}: {content}")
                    background_tasks.add_task(process_and_broadcast_message, jid, msg_obj)

                    # Se vier nome no webhook, atualiza!
                    if data.get("pushName"):
                        if jid in CONVERSATION_STATE_STORE:
                            CONVERSATION_STATE_STORE[jid]["name"] = data.get("pushName")
                            save_to_redis(jid)
    except Exception as e:
        print_error(f"Webhook error: {e}")
        traceback.print_exc()
    return {"status": "ok"}


class CreateTenantSchema(BaseModel):
    company_name: str
    company_slug: str  # ID único (ex: padaria-joao)
    admin_username: str
    admin_password: str


@app.get("/admin/dashboard")
async def get_admin_dashboard(admin: User = Depends(verify_super_admin)):
    db = database.SessionLocal()
    try:
        tenants = db.query(database.TenantDB).filter(database.TenantDB.id != "admin_master").all()

        # LOGICA NOVA: Conta apenas usuários que NÃO começam com 'admin'
        total_users = db.query(database.UserDB).filter(
            not_(database.UserDB.username.ilike("admin%"))
        ).count()

        tenants_list = []
        for t in tenants:
            tenants_list.append({
                "id": t.id,
                "name": t.name,
                "instance": t.instance_name,
                "created_at": t.created_at.strftime("%d/%m/%Y") if t.created_at else "N/A",
                "status": "active"
            })

        return {
            "metrics": {
                "total_tenants": len(tenants),
                "total_users": total_users,
                "active_instances": len([t for t in tenants if t.instance_name])
            },
            "tenants": tenants_list
        }
    finally:
        db.close()


@app.get("/admin/users_global")
async def get_all_global_users(admin: User = Depends(verify_super_admin)):
    """Lista todos os usuários de todos os tenants (exceto admins)"""
    db = database.SessionLocal()
    try:
        # Faz um JOIN para pegar o nome da empresa também
        # Filtra quem começa com 'admin'
        results = db.query(database.UserDB, database.TenantDB).join(
            database.TenantDB, database.UserDB.tenant_id == database.TenantDB.id
        ).filter(
            not_(database.UserDB.username.ilike("admin%"))
        ).all()

        users_list = []
        for user, tenant in results:
            users_list.append({
                "username": user.username,
                "full_name": user.full_name,
                "tenant_name": tenant.name,  # Nome da Empresa
                "tenant_id": tenant.id
            })

        return users_list
    except Exception as e:
        print_error(f"Erro global users: {e}")
        return []
    finally:
        db.close()


@app.post("/admin/create_tenant")
async def create_new_tenant(req: CreateTenantSchema, admin: User = Depends(verify_super_admin)):
    # Validação básica do slug
    if " " in req.company_slug:
        raise HTTPException(status_code=400, detail="ID do sistema não pode ter espaços.")

    instance_name = f"cosmos-{req.company_slug}"

    print_info(f"🏢 Iniciando criação: {req.company_name} ({instance_name})")

    # 1. Cria Instância
    evo_data = await create_evolution_instance(instance_name)

    # Se falhou ou retornou lixo, aborta
    if not evo_data or not isinstance(evo_data, dict):
        raise HTTPException(status_code=502, detail="Falha ao criar instância no WhatsApp (Erro na Evolution API)")

    # Extração segura dos dados (com .get e valores padrão)
    # A estrutura do retorno pode variar (hash vs token), então tentamos ambos
    instance_id = evo_data.get("instance", {}).get("instanceId")

    # Extração Inteligente da API Key
    raw_hash = evo_data.get("hash")

    if isinstance(raw_hash, dict):
        # Formato antigo: {"hash": {"apikey": "..."}}
        api_key = raw_hash.get("apikey")
    elif isinstance(raw_hash, str):
        # Formato novo: {"hash": "TOKEN_DIRETO"}
        api_key = raw_hash
    else:
        # Fallback
        api_key = evo_data.get("token")

    if not api_key:
        # Fallback: Se a API não retornou a key na criação (algumas versões não retornam),
        # podemos definir uma padrão ou buscar novamente.
        # Por segurança, vamos logar o erro.
        print_error(f"Evolution não retornou API Key. Resp completa: {evo_data}")
        # Tenta usar a chave global temporariamente ou falha
        # api_key = "TOKEN_PADRAO_SE_QUISER"
        raise HTTPException(status_code=502, detail="Evolution API criou a instância mas não retornou a API Key.")

    db = database.SessionLocal()
    try:
        # 2. Salva Tenant
        new_tenant = database.TenantDB(
            id=req.company_slug,
            name=req.company_name,
            instance_name=instance_name,
            instance_id=instance_id,
            instance_token=api_key,
            type="CLIENT"
        )
        db.add(new_tenant)

        # 3. Salva Admin da Empresa
        new_user = database.UserDB(
            username=req.admin_username,
            full_name=f"Admin {req.company_name}",
            hashed_password=security.get_password_hash(req.admin_password),
            tenant_id=req.company_slug,
            disabled=False
        )
        db.add(new_user)

        db.commit()
        return {"status": "success", "message": "Empresa criada com sucesso!"}

    except Exception as e:
        db.rollback()
        print_error(f"Erro Banco: {e}")
        # Verifica se é erro de duplicidade
        if "psycopg2.errors.UniqueViolation" in str(e):
            raise HTTPException(status_code=400, detail="ID da empresa ou Usuário já existem.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)