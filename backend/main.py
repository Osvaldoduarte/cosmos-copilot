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


def normalize_jid(jid: str) -> str:
    """
    Normaliza JID para formato padrão @s.whatsapp.net.
    Converte @lid (novo formato WhatsApp) para @s.whatsapp.net
    para evitar conversas duplicadas.
    """
    if not jid:
        return jid
    
    # Se já está no formato padrão, retorna
    if '@s.whatsapp.net' in jid:
        return jid
    
    # Converte @lid para @s.whatsapp.net (REMOVIDO: LID != Número de telefone)
    # if '@lid' in jid:
    #     number = jid.split('@')[0]
    #     return f"{number}@s.whatsapp.net"
    
    # Para grupos (@g.us) e outros formatos, mantém original
    return jid



# --- Carregamento de Variáveis ---
EVO_URL = os.getenv("EVOLUTION_API_URL")
# EVO_INSTANCE removed - multi-tenant app uses tenant.instance_name from database
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
from core.state import CONVERSATION_STATE_STORE, STATE_LOCK

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
    tokens_used: int = 0

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

origins = ["*"]

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
        "tenant": user_db.tenant,
        "tokens_used": user_db.tokens_used
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
                instance_data = resp.json()
                
                # 🔥 CONFIGURAR WEBHOOK AUTOMATICAMENTE
                print_info(f"🔗 Configurando webhook para {instance_name}...")
                webhook_url = "https://cosmos-backend-129644477821.us-central1.run.app/webhook/evolution"
                webhook_payload = {
                    "webhook": {
                        "enabled": True,
                        "url": webhook_url,
                        "webhookByEvents": False,
                        "webhookBase64": False,
                        "events": [
                            "QRCODE_UPDATED",
                            "MESSAGES_UPSERT",
                            "MESSAGES_UPDATE",
                            "SEND_MESSAGE",
                            "CONNECTION_UPDATE"
                        ]
                    }
                }
                
                webhook_resp = await client.post(
                    f"{EVO_URL}/webhook/set/{instance_name}",
                    headers=headers,
                    json=webhook_payload,
                    timeout=10.0
                )
                
                if webhook_resp.status_code in [200, 201]:
                    print_success(f"✅ Webhook configurado: {webhook_url}")
                else:
                    print_warning(f"⚠️ Webhook não configurado: {webhook_resp.status_code} - {webhook_resp.text}")
                
                return instance_data  # Sucesso: Retorna Dict
                
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
            {
                "username": u.username, 
                "full_name": u.full_name, 
                "disabled": u.disabled,
                "metrics": {
                    "ai_usage": f"{u.tokens_used}",
                    "clients_month": 0, # Placeholder
                    "response": "Em breve",
                    "pie": {"text": 100, "audio": 0, "image": 0, "video": 0},
                    "messages": {"text": 0, "audio": 0, "image": 0, "video": 0, "total": 0}
                }
            }
            for u in company_users
        ]
    finally:
        db.close()

    # 3. Calcular Métricas
    total_tokens = sum(u.tokens_used for u in company_users)
    active_clients_count = len(CONVERSATION_STATE_STORE) # Aproximação baseada na memória atual

    return {
        "company_name": current_user.tenant.name,
        "instance_name": current_user.tenant.instance_name,
        "connection_status": instance_status,
        "globalMetrics": {
            "active_clients": active_clients_count,
            "avg_response": "Em breve",
            "total_ai": f"{total_tokens}",
            "total_team": len(company_users)
        },
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
                    # 1. Tenta buscar mensagens (Aumentado para 100 para garantir histórico recente completo)
                    payload = {
                        "where": {"key": {"remoteJid": jid}},
                        "limit": 100,
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
                                # Log para debug de mensagens perdidas
                                if "opa ja vejo" in content.lower():
                                    print_success(f"   🎯 ENCONTRADA: {content} (ID: {m.get('key', {}).get('id')})")
                                
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
                            # --- LÓGICA DELTA (OTIMIZAÇÃO) ---
                            existing_data = CONVERSATION_STATE_STORE.get(jid)
                            
                            if existing_data:
                                # 1. Recupera mensagens antigas
                                old_msgs = existing_data.get("messages", [])
                                old_ids = {m["message_id"] for m in old_msgs}
                                
                                # 2. Filtra apenas as novas (que não temos)
                                new_msgs = [m for m in processed_msgs if m["message_id"] not in old_ids]
                                
                                if not new_msgs:
                                    print_info(f"   ⏩ {chat_name}: Nenhuma mensagem nova. Pulando update.")
                                    continue # Pula para o próximo JID
                                    
                                # 3. Mescla e Ordena
                                final_msgs = old_msgs + new_msgs
                                final_msgs.sort(key=lambda x: x["timestamp"])
                                
                                # 4. Atualiza Estado
                                CONVERSATION_STATE_STORE[jid]["messages"] = final_msgs
                                CONVERSATION_STATE_STORE[jid]["lastUpdated"] = final_msgs[-1]["timestamp"] * 1000
                                # Atualiza metadados se mudaram
                                if chat_name: CONVERSATION_STATE_STORE[jid]["name"] = chat_name
                                if avatar: CONVERSATION_STATE_STORE[jid]["avatar_url"] = avatar
                                
                                print_success(f"   ➕ {chat_name}: Adicionadas {len(new_msgs)} novas msgs (Total: {len(final_msgs)}).")
                                
                            else:
                                # Se não existe, cria do zero
                                CONVERSATION_STATE_STORE[jid] = {
                                    "name": chat_name,
                                    "avatar_url": avatar,
                                    "messages": processed_msgs,
                                    "unread": False,
                                    "lastUpdated": processed_msgs[-1]["timestamp"] * 1000
                                }
                                print_success(f"   💾 {chat_name}: Criado com {len(processed_msgs)} msgs.")

                        # Salva no Redis (ÚNICO PONTO DE ESCRITA)
                        save_to_redis(jid)

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

async def fetch_profile_picture_background(jid: str, instance_name: str):
    """
    Busca a foto do perfil em background e atualiza o estado.
    """
    if not instance_name or not EVO_URL:
        return

    # Evita busca repetida se já tiver URL (double check)
    if jid in CONVERSATION_STATE_STORE and CONVERSATION_STATE_STORE[jid].get("avatar_url"):
        return

    print_info(f"📸 Buscando foto para {jid} em background...")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"apikey": EVO_TOKEN} # Usa token global por enquanto
            
            # Busca foto
            number = jid.split('@')[0]
            resp = await client.get(
                f"{EVO_URL}/chat/findPicture/{instance_name}/{number}",
                headers=headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                picture_url = data.get("picture")
                
                if picture_url:
                    async with STATE_LOCK:
                        if jid in CONVERSATION_STATE_STORE:
                            CONVERSATION_STATE_STORE[jid]["avatar_url"] = picture_url
                            save_to_redis(jid)
                            
                            # Broadcast update de perfil
                            await manager.broadcast({
                                "type": "profile_update",
                                "conversation_id": jid,
                                "avatar_url": picture_url,
                                "name": CONVERSATION_STATE_STORE[jid].get("name")
                            })
                    print_success(f"📸 Foto atualizada para {jid}")
    except Exception as e:
        print_error(f"Erro ao buscar foto em background: {e}")


async def process_and_broadcast_message(conversation_id: str, message_obj: Dict[str, Any], instance_name: str = None):
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

            # Verifica duplicidade antes de adicionar
            existing_ids = {m["message_id"] for m in CONVERSATION_STATE_STORE[conversation_id]["messages"]}
            
            if message_obj["message_id"] not in existing_ids:
                CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)
                CONVERSATION_STATE_STORE[conversation_id]["lastUpdated"] = message_obj.get("timestamp",
                                                                                           int(time.time())) * 1000
                if message_obj.get("sender") == "cliente":
                    CONVERSATION_STATE_STORE[conversation_id]["unread"] = True
                    CONVERSATION_STATE_STORE[conversation_id]["unreadCount"] = CONVERSATION_STATE_STORE[
                                                                                   conversation_id].get("unreadCount",
                                                                                                        0) + 1
            else:
                print_warning(f"⚠️ Mensagem duplicada ignorada: {message_obj['message_id']}")
                return # Sai se for duplicada para não salvar/broadcastar à toa

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

        # 📸 Se não tem avatar e temos instance_name, agenda busca em background
        if not CONVERSATION_STATE_STORE[conversation_id].get("avatar_url") and instance_name:
            asyncio.create_task(fetch_profile_picture_background(conversation_id, instance_name))

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
                msgs_resp = await client.post(f"{EVO_URL}/chat/findMessages/{instance_name}", headers=headers,
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
                contacts_resp = await client.post(f"{EVO_URL}/chat/findContacts/{instance_name}", headers=headers,
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
                    
                    # --- LÓGICA DELTA (OTIMIZAÇÃO) ---
                    if jid in CONVERSATION_STATE_STORE:
                        old_msgs = CONVERSATION_STATE_STORE[jid].get("messages", [])
                        old_ids = {m["message_id"] for m in old_msgs}
                        
                        # Filtra novas
                        new_msgs = [m for m in processed_msgs if m["message_id"] not in old_ids]
                        
                        if new_msgs:
                            final_msgs = old_msgs + new_msgs
                            final_msgs.sort(key=lambda x: x["timestamp"])
                            CONVERSATION_STATE_STORE[jid]["messages"] = final_msgs
                            CONVERSATION_STATE_STORE[jid]["lastUpdated"] = final_msgs[-1]["timestamp"] * 1000
                        
                        # Atualiza metadados sempre (pode ter mudado foto/nome)
                        CONVERSATION_STATE_STORE[jid]["name"] = final_name
                        CONVERSATION_STATE_STORE[jid]["avatar_url"] = contact.get("profilePicUrl") or ""
                        
                    else:
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

    # --- AUTO-CONFIGURAÇÃO DE WEBHOOK (CLOUD RUN) ---
    public_url = os.getenv("PUBLIC_URL")
    if public_url:
        print_info(f"🌍 PUBLIC_URL detectada: {public_url}")
        print_info("⚙️ Configurando webhook automaticamente...")
        
        try:
            webhook_url = f"{public_url}/webhook/evolution"
            # Remove trailing slash se houver duplicidade
            webhook_url = webhook_url.replace("//webhook", "/webhook")
            
            headers = {
                "apikey": EVO_TOKEN,
                "Content-Type": "application/json"
            }
            
            webhook_config = {
                "webhook": {
                    "enabled": True,
                    "url": webhook_url,
                    "webhook_by_events": False,
                    "webhook_base64": False,
                    "events": [
                        "QRCODE_UPDATED",
                        "MESSAGES_UPSERT",
                        "MESSAGES_UPDATE",
                        "MESSAGES_DELETE",
                        "SEND_MESSAGE",
                        "CONNECTION_UPDATE"
                    ]
                }
            }
            
            # Usa httpx para fazer a requisição async
            async with httpx.AsyncClient() as client:
                # Primeiro busca instâncias se EVO_INSTANCE não estiver definido
                target_instance = EVO_INSTANCE
                if not target_instance:
                    resp = await client.get(f"{EVO_URL}/instance/fetchInstances", headers=headers)
                    if resp.status_code == 200:
                        instances = resp.json()
                        if instances:
                            target_instance = instances[0].get("instance", {}).get("instanceName") or instances[0].get("name")
                
                if target_instance:
                    resp = await client.post(
                        f"{EVO_URL}/webhook/set/{target_instance}",
                        headers=headers,
                        json=webhook_config,
                        timeout=10.0
                    )
                    
                    if resp.status_code in [200, 201]:
                        print_success(f"✅ Webhook configurado para: {webhook_url}")
                    else:
                        print_error(f"❌ Falha ao configurar webhook: {resp.text}")
                else:
                    print_warning("⚠️ Nenhuma instância encontrada para configurar webhook.")
                    
        except Exception as e:
            print_error(f"❌ Erro na auto-configuração do webhook: {e}")


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
    print(f"🔌 Nova conexão WebSocket recebida: {websocket.client}")
    await manager.connect(websocket)
    print(f"✅ WebSocket aceito e conectado!")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"🔴 WebSocket desconectado")
        manager.disconnect(websocket)


# --- Instância ---
@app.get("/evolution/instance/status")
async def get_instance_status(current_user: User = Depends(get_current_active_user)):
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    url = f"{EVO_URL}/instance/connectionState/{current_user.tenant.instance_name}"
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
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    async with httpx.AsyncClient() as client:
        await client.delete(f"{EVO_URL}/instance/logout/{current_user.tenant.instance_name}", headers={"apikey": EVO_TOKEN})
    return {"status": "logged_out"}






# --- Sync ---
@app.post("/sync/initial_load")
async def initial_load(current_user: User = Depends(get_current_active_user)):
    """
    Carga inicial LGPD-compliant com verificação de instância.
    ⚠️ ATENÇÃO: Só carrega se NÃO houver conversas antigas!
    """
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    
    # 🔒 VERIFICAÇÃO LGPD: Bloqueia se já tiver conversas (podem ser de outra instância!)
    async with STATE_LOCK:
        existing_count = len(CONVERSATION_STATE_STORE)
    
    if existing_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"⚠️ LGPD: {existing_count} conversas já carregadas! DELETE TUDO primeiro usando /conversations/clear_all para evitar misturar dados de diferentes WhatsApps!"
        )
    
    print_warning(f"🔒 LGPD: Verificando instância {instance_name}...")
    
    # Verifica se a instância está conectada
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            status_resp = await client.get(
                f"{EVO_URL}/instance/connectionState/{instance_name}",
                headers={"apikey": api_token}
            )
            
            print_info(f"Status code: {status_resp.status_code}")
            
            if status_resp.status_code == 404:
                print_error(f"Instância {instance_name} não encontrada na Evolution API")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Instância '{instance_name}' não existe. Verifique o nome da instância ou crie uma nova."
                )
            
            if status_resp.status_code != 200:
                error_text = status_resp.text
                print_error(f"Erro ao verificar instância: {status_resp.status_code} - {error_text}")
                raise HTTPException(
                    status_code=500, 
                    detail=f"Evolution API retornou erro {status_resp.status_code}: {error_text}"
                )
            
            status_data = status_resp.json()
            state = status_data.get("state", status_data.get("instance", {}).get("state"))
            
            print_info(f"Estado da instância: {state}")
            
            if state != "open":
                print_warning(f"WhatsApp não conectado. Estado atual: {state}")
                raise HTTPException(
                    status_code=400,
                    detail=f"WhatsApp não conectado! Estado: {state}. Conecte o QR code primeiro."
                )
            
            print_success(f"✅ Instância {instance_name} conectada e verificada")
    
    except httpx.HTTPError as e:
        print_error(f"Erro de rede ao verificar instância: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro de conexão com Evolution API: {str(e)}")
    
    print_info(f"🚀 Carga inicial LGPD para {instance_name}...")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"apikey": api_token}
            
            # 🔥 APENAS mensagens recentes (últimas 48h)
            import time
            two_days_ago = int(time.time()) - (48 * 3600)
            
            print_info(f"📥 Buscando mensagens das últimas 48h (desde {two_days_ago})...")
            msgs_resp = await client.post(
                f"{EVO_URL}/chat/findMessages/{instance_name}",
                headers=headers,
                json={
                    "where": {
                        "messageTimestamp": {"$gte": two_days_ago}
                    },
                    "limit": 200  # Mais mensagens para pegar mais conversas
                }
            )
            
            if msgs_resp.status_code != 200:
                raise HTTPException(status_code=500, detail="Erro ao buscar mensagens")
            
            messages_data = msgs_resp.json().get("messages", {}).get("records", [])
            print_info(f"📊 {len(messages_data)} mensagens recentes encontradas")
            
            # Agrupa por JID
            conversations_map = {}
            for m in messages_data:
                key = m.get("key", {})
                
                # Extrai JID
                possible_jids = []
                if key.get("remoteJid"): possible_jids.append(key.get("remoteJid"))
                if key.get("remoteJidAlt"): possible_jids.append(key.get("remoteJidAlt"))
                
                # Filtra JIDs válidos
                valid_jids = [j for j in possible_jids if "@s.whatsapp.net" in j and "232" not in j[:3]]
                
                if not valid_jids:
                    continue
                
                jid = min(valid_jids, key=len)  # Menor JID (phone number)
                
                # Filtros
                if "@g.us" in jid or "status@broadcast" in jid:
                    continue
                
                number = jid.split('@')[0]
                if not number.isdigit() or len(number) < 10 or len(number) > 15:
                    continue
                
                # REMOVIDO FILTRO DE APENAS BRASILEIROS (554)
                # if not number.startswith('554'):
                #     continue
                
                # Adiciona à conversa
                if jid not in conversations_map:
                    conversations_map[jid] = []
                
                # Extrai conteúdo
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
                    elif "videoMessage" in msg_content:
                        content = "🎥 [Vídeo]"
                    elif "documentMessage" in msg_content:
                        content = "📄 [Documento]"
                    elif "stickerMessage" in msg_content:
                        content = "👾 [Figurinha]"
                
                if content:
                    conversations_map[jid].append({
                        "content": content,
                        "sender": "vendedor" if key.get("fromMe") else "cliente",
                        "timestamp": m.get("messageTimestamp"),
                        "message_id": key.get("id"),
                        "pushName": m.get("pushName", "")
                    })
            
            # Limita a 20 conversas mais ativas
            sorted_jids = sorted(
                conversations_map.keys(),
                key=lambda j: len(conversations_map[j]),
                reverse=True
            )[:20]
            
            print_info(f"📊 Carregando {len(sorted_jids)} conversas com mensagens recentes...")
            
            loaded_count = 0
            async with STATE_LOCK:
                for jid in sorted_jids:
                    try:
                        msgs = conversations_map[jid]
                        number = jid.split('@')[0]
                        
                        # Ordena e limita a 40
                        msgs.sort(key=lambda x: x["timestamp"])
                        msgs = msgs[-40:]  # Últimas 40
                        
                        # Nome (pega do pushName da última mensagem)
                        name = None
                        for msg in reversed(msgs):
                            if msg.get("pushName"):
                                name = msg["pushName"]
                                break
                        
                        if not name:
                            name = f"+{number}"
                        
                        # Remove pushName das mensagens
                        for msg in msgs:
                            msg.pop("pushName", None)
                        
                        # Salva no store
                        CONVERSATION_STATE_STORE[jid] = {
                            "name": name,
                            "avatar_url": "",  # Não buscar foto para ser mais rápido
                            "messages": msgs,
                            "unread": False,
                            "unreadCount": 0,
                            "lastUpdated": msgs[-1]["timestamp"] * 1000 if msgs else int(time.time() * 1000)
                        }
                        
                        save_to_redis(jid)
                        loaded_count += 1
                        print_success(f"✅ {name} ({number}): {len(msgs)} mensagens")
                    
                    except Exception as e:
                        print_error(f"❌ Erro ao processar {jid}: {e}")
                        continue
            
            print_success(f"🎉 {loaded_count} conversas recentes carregadas!")
            return {
                "status": "success",
                "loaded": loaded_count,
                "period": "últimas 48 horas"
            }
    
    except Exception as e:
        print_error(f"❌ Erro na carga inicial: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/active_conversations")
async def sync_active_conversations(current_user: User = Depends(get_current_active_user)):
    """
    Sincroniza APENAS conversas que já existem no Redis/memória.
    Evita pegar TODOS os contatos da Evolution API.
    """
    if not current_user.tenant or not current_user.tenant.instance_name:
        raise HTTPException(status_code=400, detail="Instância não configurada")
    
    instance_name = current_user.tenant.instance_name
    api_token = current_user.tenant.instance_token or EVO_TOKEN
    
    # Pega apenas JIDs que já existem
    existing_jids = []
    async with STATE_LOCK:
        existing_jids = [jid for jid in CONVERSATION_STATE_STORE.keys() if "@s.whatsapp.net" in jid]
    
    if not existing_jids:
        return {"status": "success", "message": "Nenhuma conversa ativa para sincronizar"}
    
    print_info(f"🔄 Sincronizando {len(existing_jids)} conversas ativas...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"apikey": api_token}
            
            for jid in existing_jids:
                try:
                    # Busca mensagens desse JID específico
                    number = jid.split('@')[0]
                    resp = await client.post(
                        f"{EVO_URL}/chat/findMessages/{instance_name}",
                        headers=headers,
                        json={"where": {"key": {"remoteJid": jid}}, "limit": 50}
                    )
                    
                    if resp.status_code == 200:
                        messages_data = resp.json().get("messages", {}).get("records", [])
                        
                        if messages_data:
                            async with STATE_LOCK:
                                old_msgs = CONVERSATION_STATE_STORE[jid].get("messages", [])
                                old_ids = {m["message_id"] for m in old_msgs}
                                
                                # Processa novas mensagens
                                new_msgs = []
                                for m in messages_data:
                                    msg_id = m.get("key", {}).get("id")
                                    if msg_id not in old_ids:
                                        content = (
                                            m.get("message", {}).get("conversation") or
                                            m.get("message", {}).get("extendedTextMessage", {}).get("text") or
                                            "📷 [Mídia]"
                                        )
                                        new_msgs.append({
                                            "content": content,
                                            "sender": "vendedor" if m.get("key", {}).get("fromMe") else "cliente",
                                            "timestamp": m.get("messageTimestamp"),
                                            "message_id": msg_id
                                        })
                                
                                if new_msgs:
                                    final_msgs = old_msgs + new_msgs
                                    final_msgs.sort(key=lambda x: x["timestamp"])
                                    CONVERSATION_STATE_STORE[jid]["messages"] = final_msgs
                                    save_to_redis(jid)
                                    print_success(f"✅ {number}: +{len(new_msgs)} mensagens")
                
                except Exception as e:
                    print_error(f"Erro ao sincronizar {jid}: {e}")
                    continue
        
        return {"status": "success", "message": f"{len(existing_jids)} conversas sincronizadas"}
    
    except Exception as e:
        print_error(f"Erro geral na sincronização: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/conversations/clear_all")
async def clear_all_conversations(current_user: User = Depends(get_current_active_user)):
    """
    Limpa TODAS as conversas ao trocar de instância/número.
    ⚠️ LGPD: Use isto ao trocar de cliente/instância!
    """
    print_warning("🗑️ Limpando TODAS as conversas (LGPD)...")
    
    # Limpa memória
    async with STATE_LOCK:
        cleared_memory = len(CONVERSATION_STATE_STORE)
        CONVERSATION_STATE_STORE.clear()
        print_success(f"✅ {cleared_memory} conversas removidas da memória")
    
    # Limpa Redis
    cleared_redis = 0
    if redis_client:
        try:
            keys = redis_client.keys("chat:*")
            for key in keys:
                redis_client.delete(key)
            cleared_redis = len(keys)
            print_success(f"✅ {cleared_redis} conversas removidas do Redis")
        except Exception as e:
            print_error(f"Erro ao limpar Redis: {e}")
    
    return {
        "status": "success",
        "message": f"Backend limpo: {cleared_memory} memória + {cleared_redis} Redis",
        "frontend_action_required": "Limpe localStorage do navegador: F12 > Application > Local Storage > Clear All"
    }

# --- Chat ---
@app.get("/conversations")
async def get_all_conversations(
        current_user: User = Depends(get_current_active_user)
):
    if not current_user.tenant or not current_user.tenant.instance_name:
        return {"status": "error", "conversations": []}

    formatted = []
    
    # 🚀 USA MEMÓRIA EM VEZ DE REDIS SCAN (muito mais rápido!)
    async with STATE_LOCK:
        for jid, data in CONVERSATION_STATE_STORE.items():
            try:
                # Filtros
                if "@g.us" in jid or "status@broadcast" in jid:
                    continue
                
                number_part = jid.split('@')[0]
                
                # Ignora números inválidos
                if not number_part.isdigit():
                    continue
                if len(number_part) < 10 or len(number_part) > 15:
                    continue
                
                # REMOVIDO FILTRO DE APENAS BRASILEIROS (554)
                # if not number_part.startswith('554'):
                #     continue
                
                # Pega a última mensagem
                messages = data.get("messages", [])
                last_msg = messages[-1]["content"] if messages else ""
                
                formatted.append({
                    "id": jid,
                    "name": data.get("name", number_part),
                    "avatar_url": data.get("avatar_url", ""),
                    "lastMessage": last_msg,
                    "unread": data.get("unread", False),
                    "unreadCount": data.get("unreadCount", 0),
                    "lastUpdated": data.get("lastUpdated", 0)
                })
            except Exception as e:
                print_error(f"Erro ao processar conversa {jid}: {e}")
                continue
    
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
        # Sempre usa a instância do tenant (multi-tenant)
        if not current_user.tenant or not current_user.tenant.instance_name:
            raise HTTPException(status_code=400, detail="Instância não configurada")
        
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



@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, current_user: User = Depends(get_current_active_user)):
    if "@" not in conversation_id and conversation_id.isdigit():
        conversation_id = f"{conversation_id}@s.whatsapp.net"
    
    print_info(f"🗑️ Deletando conversa: {conversation_id}")
    
    # Remove da memória
    async with STATE_LOCK:
        if conversation_id in CONVERSATION_STATE_STORE:
            del CONVERSATION_STATE_STORE[conversation_id]
    
    # Remove do Redis
    if redis_client:
        try:
            redis_client.delete(f"chat:{conversation_id}")
        except Exception as e:
            print_error(f"Erro ao deletar do Redis: {e}")
            
    return {"status": "success"}

@app.post("/conversations/{jid:path}/mark_read")
async def mark_conversation_as_read(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Marca todas as mensagens de uma conversa como lidas.
    Remove a bolinha de 'não lido' da conversa.
    """
    # Normaliza o JID
    if "@" not in jid and jid.isdigit():
        target_jid = f"{jid}@s.whatsapp.net"
    else:
        target_jid = jid
    
    real_jid = find_existing_conversation_jid(target_jid) or target_jid
    print_info(f"📖 Marcando conversa como lida: {real_jid}")
    
    async with STATE_LOCK:
        if real_jid in CONVERSATION_STATE_STORE:
            # Marca conversa como lida
            CONVERSATION_STATE_STORE[real_jid]["unread"] = False
            CONVERSATION_STATE_STORE[real_jid]["unread_count"] = 0
            
            # Salva no Redis
            save_to_redis(real_jid)
            
            print_success(f"✅ Conversa {real_jid} marcada como lida")
            
            # Notifica via WebSocket
            await manager.broadcast({
                "type": "conversation_read",
                "conversation_id": real_jid
            })
            
            return {"status": "success", "conversation_id": real_jid}
        else:
            print_warning(f"⚠️  Conversa {real_jid} não encontrada")
            return {"status": "not_found", "conversation_id": real_jid}


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
    async with STATE_LOCK:
        if jid not in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[jid] = {"messages": [], "name": number, "unread": False}
        
        # Adiciona a mensagem enviada
        CONVERSATION_STATE_STORE[jid]["messages"].append({
            "content": request.initial_message,
            "sender": "vendedor",
            "timestamp": int(time.time()),
            "message_id": f"sent_{int(time.time())}"
        })

    return {"status": "success", "conversation_id": jid}

# --- SEARCH ENDPOINT ---
from thefuzz import process, fuzz

@app.get("/conversations/search")
async def search_conversations(q: str, limit: int = 10, current_user: User = Depends(get_current_active_user)):
    if not q:
        return []
    
    results = []
    query = q.lower()
    
    # Snapshot dos dados para busca
    conversations = []
    async with STATE_LOCK:
        for jid, data in CONVERSATION_STATE_STORE.items():
            conversations.append({
                "id": jid,
                "name": data.get("name", jid.split('@')[0]),
                "messages": data.get("messages", [])
            })
            
    # 1. Busca por Nome (Fuzzy)
    names_dict = {c["id"]: c["name"] for c in conversations}
    matched_names = process.extractBests(query, names_dict, scorer=fuzz.partial_ratio, score_cutoff=65, limit=limit)
    
    matched_ids = set()
    for name, score, jid in matched_names:
        matched_ids.add(jid)
        results.append({
            "id": jid,
            "name": name,
            "match_type": "name",
            "score": score,
            "snippet": None,
            "timestamp": int(time.time())
        })
        
    # 2. Busca por Conteúdo (Mensagens)
    if len(results) < limit:
        for c in conversations:
            if c["id"] in matched_ids:
                continue
            
            for msg in reversed(c["messages"]):
                content = msg.get("content", "")
                if not content: continue
                
                if query in content.lower():
                    results.append({
                        "id": c["id"],
                        "name": c["name"],
                        "match_type": "message",
                        "score": 100,
                        "snippet": content[:60] + "..." if len(content) > 60 else content,
                        "timestamp": msg.get("timestamp", 0)
                    })
                    matched_ids.add(c["id"])
                    break
    
    # Preenche dados faltantes
    final_results = []
    for r in results:
        original = next((c for c in conversations if c["id"] == r["id"]), None)
        if original:
            last_msg = original["messages"][-1] if original["messages"] else None
            last_msg_content = last_msg.get("content", "") if last_msg else ""
            
            final_results.append({
                **r,
                "avatar_url": CONVERSATION_STATE_STORE.get(r["id"], {}).get("avatar_url", ""),
                "unreadCount": 0,
                "lastMessage": r["snippet"] or last_msg_content,
                "lastUpdated": r.get("timestamp") or (last_msg.get("timestamp") if last_msg else 0) * 1000
            })
            
    return final_results

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
        # Calcular Tokens (Estimativa: 1 token ~= 4 caracteres)
        input_tokens = len(user_query) // 4
        output_tokens = len(str(result)) // 4
        total_tokens = input_tokens + output_tokens
        
        # Atualizar Banco de Dados
        db = database.SessionLocal()
        try:
            db.query(database.UserDB).filter(database.UserDB.username == current_user.username).update(
                {"tokens_used": database.UserDB.tokens_used + total_tokens}
            )
            db.commit()
            print_success(f"💰 Tokens contabilizados: {total_tokens} (Total User: {current_user.tokens_used + total_tokens})")
        except Exception as e:
            print_error(f"Erro ao salvar tokens: {e}")
            db.rollback()
        finally:
            db.close()

        return result
    except Exception as e:
        print_error(f"❌ [API] Erro ao gerar sugestão: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao processar IA: {str(e)}")


from services.media_service import media_service

async def process_media_and_update(jid: str, message_id: str, media_type: str):
    """
    Processa mídia em background e atualiza a mensagem com a transcrição/descrição.
    """
    try:
        # Usa as globais EVO_INSTANCE, EVO_URL, EVO_TOKEN
        transcription = await media_service.process_media(
            message_id, 
            EVO_INSTANCE, 
            EVO_URL, 
            EVO_TOKEN, 
            media_type
        )
        
        if transcription:
            prefix = "🎤 [Áudio]" if "audio" in media_type else "📷 [Imagem]" if "image" in media_type else "🎥 [Vídeo]"
            new_content = f"{prefix} {transcription}"
            
            async with STATE_LOCK:
                if jid in CONVERSATION_STATE_STORE:
                    messages = CONVERSATION_STATE_STORE[jid].get("messages", [])
                    for msg in messages:
                        if msg["message_id"] == message_id:
                            msg["content"] = new_content
                            print_success(f"✏️ Mensagem {message_id} atualizada com transcrição.")
                            
                            # Broadcast Update (Frontend agora aceita update se ID existir)
                            await manager.broadcast({
                                "type": "new_message",
                                "conversation_id": jid,
                                "message": msg,
                                "name": CONVERSATION_STATE_STORE[jid].get("name"),
                                "avatar_url": CONVERSATION_STATE_STORE[jid].get("avatar_url"),
                                "unreadCount": CONVERSATION_STATE_STORE[jid].get("unreadCount", 0)
                            })
                            break
            
            save_to_redis(jid)
            
    except Exception as e:
        print_error(f"Erro ao atualizar transcrição: {e}")

@app.post("/webhook/evolution")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        print_info(f"🔍 Webhook Payload Recebido: {json.dumps(body, indent=2)}")
        event = body.get("event")
        data = body.get("data")
        
        print_info(f"⚡ Evento Webhook: {event}")
        
        if not data: 
            print_warning("⚠️ Webhook sem dados!")
            return {"status": "no_data"}

        if event == "messages.upsert":
            msg_data = data.get("message") or {}
            key = data.get("key") or {}

            # 🎭 Processar Reações
            if "reactionMessage" in msg_data:
                # ... (código de reação mantido igual, omitido aqui para brevidade se não for mudar) ...
                # Vou manter o bloco original de reação se ele não for substituído pelo diff
                reaction_data = msg_data["reactionMessage"]
                target_msg_id = reaction_data.get("key", {}).get("id")
                emoji = reaction_data.get("text", "")
                jid_raw = key.get("remoteJidAlt") or key.get("remoteJid")
                jid = normalize_jid(jid_raw)  # Normalizar JID
                from_me = key.get("fromMe", False)
                
                if target_msg_id and jid:
                    who = "vendedor" if from_me else "cliente"
                    print_info(f"👍 Webhook: Reação '{emoji}' de {who} na mensagem {target_msg_id}")
                    
                    async with STATE_LOCK:
                        if jid in CONVERSATION_STATE_STORE:
                            messages = CONVERSATION_STATE_STORE[jid].get("messages", [])
                            for msg in messages:
                                if msg.get("message_id") == target_msg_id:
                                    if "reactions" not in msg: msg["reactions"] = []
                                    msg["reactions"] = [r for r in msg["reactions"] if r.get("from") != who]
                                    if emoji:
                                        msg["reactions"].append({"emoji": emoji, "from": who})
                                        print_success(f"✅ Reação adicionada à mensagem {target_msg_id}")
                                    save_to_redis(jid)
                                    await manager.broadcast({
                                        "type": "message_reaction",
                                        "conversation_id": jid,
                                        "message_id": target_msg_id,
                                        "reaction": emoji,
                                        "from": who
                                    })
                                    break
                return {"status": "ok"}

            # 🚨 REMOVIDO FILTRO 'fromMe' PARA DEBUG E SYNC COMPLETO
            # if not key.get("fromMe"):
            
            # Prioriza JID padrão (@s.whatsapp.net) e evita LIDs (que são números longos)
            # Estratégia: Coleta todos os JIDs possíveis e escolhe o menor (Phone Number < LID)
            possible_jids = []
            
            if key.get("remoteJid"): possible_jids.append(key.get("remoteJid"))
            if key.get("remoteJidAlt"): possible_jids.append(key.get("remoteJidAlt"))
            if key.get("participant"): possible_jids.append(key.get("participant"))
            
            # Filtra apenas JIDs de usuário válidos
            valid_jids = [
                j for j in possible_jids 
                if j and "@s.whatsapp.net" in j and "232" not in j[:3] # 232 é prefixo comum de LID
            ]
            
            if valid_jids:
                # Escolhe o menor (número de telefone é menor que LID)
                jid_raw = min(valid_jids, key=len)
            else:
                # Fallback
                jid_raw = key.get("remoteJid") or key.get("remoteJidAlt")

            jid = normalize_jid(jid_raw)
            from_me = key.get("fromMe", False)
            
            print_info(f"📨 Webhook Upsert: JID={jid} (raw={jid_raw}) FromMe={from_me} ID={key.get('id')}")

            content = (
                msg_data.get("conversation") or
                msg_data.get("extendedTextMessage", {}).get("text") or
                msg_data.get("imageMessage", {}).get("caption")
            )

            media_type = None
            # Fallbacks para mídia sem legenda
            if not content:
                if "imageMessage" in msg_data:
                    content = "📷 [Imagem]"
                    media_type = "image"
                elif "audioMessage" in msg_data:
                    content = "🎤 [Áudio]"
                    media_type = "audio"
                elif "videoMessage" in msg_data:
                    content = "🎥 [Vídeo]"
                    media_type = "video"
                elif "documentMessage" in msg_data:
                    content = "📄 [Documento]"
                elif "stickerMessage" in msg_data:
                    content = "👾 [Figurinha]"

            if jid and content:
                ts = data.get("messageTimestamp") or int(time.time())
                
                # Determina quem enviou
                sender = "vendedor" if from_me else "cliente"
                
                msg_obj = {
                    "content": content,
                    "sender": sender,
                    "timestamp": ts,
                    "message_id": key.get("id")
                }

                print_info(f"📩 Webhook Processando: {sender} -> {jid}: {content[:30]}...")
                background_tasks.add_task(process_and_broadcast_message, jid, msg_obj, instance_name)
                
                # 🧠 Se for mídia, processa em background
                if media_type:
                    background_tasks.add_task(process_media_and_update, jid, msg_obj["message_id"], media_type)

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