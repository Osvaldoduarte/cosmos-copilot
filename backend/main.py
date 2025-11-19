import os, time, httpx, uuid, json, uvicorn, asyncio, copy
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

# Seus módulos internos
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
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

# --- Estado Global ---
STATE_LOCK = asyncio.Lock()
CONVERSATION_STATE_STORE: Dict[str, Any] = {}


# --- Modelos Pydantic ---
class NewConversationRequest(BaseModel):
    recipient_number: str
    initial_message: str


class MessageSendRequest(BaseModel):
    conversation_id: str
    message_text: str


class InstanceCreateRequest(BaseModel):
    instanceName: str


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    tenant_id: str


class AIQueryRequest(BaseModel):
    conversation_id: str
    query: Optional[str] = None
    type: str = "analysis"  # analysis | internal


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
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ===================================================================
# 1. SEGURANÇA
# ===================================================================

def authenticate_user(username: str, password: str) -> Optional[User]:
    user_data = database.get_user(username)
    if not user_data: return None
    if not security.verify_password(password, user_data.get("hashed_password")): return None
    return User(**user_data)


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
    user_data = database.get_user(username=username)
    if user_data is None: raise credentials_exception
    return User(**user_data)


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


async def send_whatsapp_message(recipient_jid: str, message_text: str) -> bool:
    number_only = recipient_jid.split('@')[0]
    url = f"{EVO_URL}/message/sendText/{EVO_INSTANCE}"
    headers = {'Content-Type': 'application/json', 'apikey': EVO_TOKEN}
    payload = {"number": number_only, "text": message_text}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            if resp.status_code in [200, 201]: return True
    except Exception as e:
        print_error(f"Falha ao enviar mensagem: {e}")
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
        
        # Broadcast via WebSocket
        await manager.broadcast({
            "type": "new_message",
            "conversation_id": conversation_id,
            "message": message_obj
        })
        
    except Exception as e:
        print_error(f"Erro processando mensagem: {e}")


# 🟢 LÓGICA ATUALIZADA DE SINCRONIZAÇÃO
async def load_history_from_evolution_api():
    await asyncio.sleep(2)
    print_info("🔄 Iniciando sincronização de histórico...")

    async with STATE_LOCK:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                headers = {"apikey": EVO_TOKEN}

                # 1. Busca Mensagens (Aumentei o limite para pegar mais contexto)
                # Vamos usar as mensagens para descobrir nomes que não estão na lista de contatos
                msgs_resp = await client.post(f"{EVO_URL}/chat/findMessages/{EVO_INSTANCE}", headers=headers,
                                              json={"limit": 100, "page": 1})
                messages_data = msgs_resp.json().get("messages", {}).get("records",
                                                                         []) if msgs_resp.status_code == 200 else []

                # Mapa auxiliar: JID -> Nome Descoberto nas Mensagens (PushName)
                discovered_names = {}

                # Processa mensagens primeiro para extrair nomes
                messages_by_jid = {}

                for m in messages_data:
                    key = m.get("key", {})
                    remote_jid = key.get("remoteJid")
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
        except Exception as e:
            print_error(f"Erro na sincronização: {e}")


# ===================================================================
# 3. ROTAS (ENDPOINTS)
# ===================================================================

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(load_history_from_evolution_api())

    # --- INICIALIZAÇÃO IA ---
    print_info("🧠 Inicializando Cérebro IA...")
    try:
        client = cerebro_ia.initialize_chroma_client()
        llm, retriever, embed, playbook = cerebro_ia.load_models(client)
        from core.shared import IA_MODELS
        IA_MODELS["llm"] = llm
        IA_MODELS["retriever"] = retriever
        IA_MODELS["embeddings"] = embed
        IA_MODELS["chroma_client"] = client
        print_success("🧠 Cérebro IA Carregado!")
    except Exception as e:
        print_error(f"Falha ao carregar IA: {e}")


# --- Auth ---
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user: raise HTTPException(status_code=401, detail="Login incorreto")
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


@app.post("/evolution/instance/create_and_get_qr")
async def create_and_get_qr(request: InstanceCreateRequest, current_user: User = Depends(get_current_active_user)):
    create_url = f"{EVO_URL}/instance/create"
    headers = {"apikey": EVO_TOKEN}
    async with httpx.AsyncClient() as client:
        await client.post(create_url, headers=headers, json={"instanceName": EVO_INSTANCE, "token": "", "qrcode": True})
        resp = await client.get(f"{EVO_URL}/instance/connect/{EVO_INSTANCE}", headers=headers)
        if resp.status_code == 200: return resp.json()
        raise HTTPException(status_code=500, detail="Falha ao gerar QR")


@app.delete("/evolution/instance/logout")
async def logout_instance(current_user: User = Depends(get_current_active_user)):
    async with httpx.AsyncClient() as client:
        await client.delete(f"{EVO_URL}/instance/logout/{EVO_INSTANCE}", headers={"apikey": EVO_TOKEN})
    return {"status": "logged_out"}


# --- Chat ---
@app.get("/conversations")
async def get_all_conversations(current_user: User = Depends(get_current_active_user)):
    formatted = []
    async with STATE_LOCK:
        print_info(f"📂 Listando conversas. Total em memória: {len(CONVERSATION_STATE_STORE)}")
        for cid, data in CONVERSATION_STATE_STORE.items():
            # Filtro básico para evitar LIDs estranhos se já tivermos o número real
            if "@lid" in cid: continue

            last_msg = ""
            if data["messages"]:
                last_msg = data["messages"][-1]["content"]

            formatted.append({
                "id": cid,
                "name": data.get("name"),
                "avatar_url": data.get("avatar_url"),
                "lastMessage": last_msg,
                "unread": data.get("unread", False),
                "unreadCount": data.get("unreadCount", 0),
                "lastUpdated": data.get("lastUpdated", 0)
            })
    formatted.sort(key=lambda x: x["lastUpdated"], reverse=True)
    return {"status": "success", "conversations": formatted}


# 🟢 ROTA INTELIGENTE DE MENSAGENS (COM SUPORTE A MÍDIA E BUSCA SOB DEMANDA)
@app.get("/conversations/{jid:path}/messages")
async def get_conversation_messages(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Busca mensagens tentando forçar a leitura do histórico antigo do WhatsApp.
    """
    # 1. Tratamento do JID
    if "@" not in jid and jid.isdigit():
        target_jid = f"{jid}@s.whatsapp.net"
    else:
        target_jid = jid

    real_jid = find_existing_conversation_jid(target_jid) or target_jid

    # 2. Verifica Memória (Cache)
    stored_msgs = []
    if real_jid in CONVERSATION_STATE_STORE:
        stored_msgs = CONVERSATION_STATE_STORE[real_jid].get("messages", [])

    # Se já temos um bom número de mensagens (ex: > 20), retornamos o cache para ser rápido
    if len(stored_msgs) > 20:
        return stored_msgs

    # 3. Se vazio ou pouco, busca na API
    print_info(f"🔍 Buscando histórico PROFUNDO para: {real_jid}")
    try:
        url = f"{EVO_URL}/chat/findMessages/{EVO_INSTANCE}"
        headers = {"apikey": EVO_TOKEN}

        # Payload Agressivo: Pede muito, sem filtro de data
        payload = {
            "where": {
                "key": {"remoteJid": real_jid}
            },
            "limit": 50,  # Tenta pegar 50 por vez
            "page": 1
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=30.0)

            messages_data = []
            if resp.status_code == 200:
                data = resp.json()
                messages_data = data.get("messages", {}).get("records", [])

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
                    processed_msgs.append({
                        "content": content,
                        "sender": "vendedor" if m.get("key", {}).get("fromMe") else "cliente",
                        "timestamp": m.get("messageTimestamp"),
                        "message_id": m.get("key", {}).get("id")
                    })

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

            return unique_msgs

    except Exception as e:
        print_error(f"Erro ao buscar histórico: {e}")

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
    success = await send_whatsapp_message(request.conversation_id, request.message_text)
    if not success: raise HTTPException(status_code=500, detail="Erro no envio")

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

    # Envia a mensagem inicial
    success = await send_whatsapp_message(jid, request.initial_message)
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



@app.post("/ai/generate_suggestion")
async def generate_ai_suggestion(request: AIQueryRequest, current_user: User = Depends(get_current_active_user)):
    copilot = cerebro_ia.get_sales_copilot()
    if not copilot:
        # Tenta recarregar se falhou no boot
        from core.shared import IA_MODELS
        if not IA_MODELS["llm"]:
             raise HTTPException(status_code=503, detail="IA não inicializada ou indisponível.")
    
    # Get conversation history
    jid = request.conversation_id
    if "@" not in jid and jid.isdigit(): jid = f"{jid}@s.whatsapp.net"
    
    history = []
    if jid in CONVERSATION_STATE_STORE:
        history = CONVERSATION_STATE_STORE[jid].get("messages", [])
        
    # Determine query
    user_query = request.query
    if not user_query and history:
        # Use last message from client if no query provided
        last_msg = next((m for m in reversed(history) if m["sender"] == "cliente"), None)
        if last_msg: user_query = last_msg["content"]
        
    if not user_query:
         return {"status": "error", "message": "Nenhuma mensagem para analisar"}

    result = copilot.generate_sales_suggestions(
        query=user_query,
        full_conversation_history=history,
        current_stage_id="unknown",
        is_private_query=(request.type == "internal"),
        client_data={}
    )
    
    return result


@app.post("/webhook/evolution")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        body = await request.json()
        # print_info(f"Webhook Payload: {json.dumps(body)}") 
        event = body.get("event")
        data = body.get("data")
        if not data: return {"status": "no_data"}

        if event == "messages.upsert":
            msg_data = data.get("message") or {}
            key = data.get("key") or {}
            
            # Ignora mensagens enviadas por mim
            if not key.get("fromMe"):
                jid = key.get("remoteJid")
                
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
    except Exception as e:
        print_error(f"Webhook error: {e}")
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)