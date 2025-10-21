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

from core import security, database, cerebro_ia

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

class NewConversationRequest(BaseModel):
    recipient_number: str = Field(..., description="Número do destinatário no formato DDI+DDD+Número, ex: 5541999999999")
    initial_message: str

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
        print(f"INFO: WebSocket conectado para a conversa {conversation_id}")

    def disconnect(self, conversation_id: str):
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            print(f"INFO: WebSocket desconectado da conversa {conversation_id}")

    async def send_personal_message(self, message: str, conversation_id: str):
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_text(message)

class SuggestionRequest(BaseModel):
    query: str
    conversation_id: str
    current_stage_id: str | None = Field(default=None)
    is_private_query: bool = Field(default=False)

class MessageSendRequest(BaseModel):
    conversation_id: str
    message_text: str

STATE_LOCK = asyncio.Lock()

CONVERSATION_STATE_STORE: Dict[str, Any] = {}

manager = ConnectionManager()
env_path = Path(__file__).parent.parent / ".env"

load_dotenv(dotenv_path=env_path)
EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")


# --- 1. Inicialização da Aplicação e Carregamento dos Modelos ---

EVO_TOKEN = os.getenv("EVOLUTION_API_KEY")

# ===================================================================
#           INÍCIO DO BLOCO DE CÓDIGO DE AUTENTICAÇÃO
# ===================================================================

# --- Configuração de Segurança ---
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # Token expira em 8 horas

# Esquema OAuth2 que aponta para o nosso novo endpoint /token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()
# --- Modelos de Dados (Pydantic) ---
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    tenant_id: str


# --- Funções Auxiliares de Autenticação ---
def authenticate_user(username: str, password: str) -> Optional[User]:
    """
    Busca o usuário e verifica a senha.
    Retorna o objeto User se for válido, senão None.
    """
    # ================== DEBUG PONTO 2: RASTREAR AUTENTICAÇÃO INTERNA ==================
    print("\n--- [DEBUG authenticate_user] Iniciando verificação ---")
    print(f"Buscando usuário: '{username}'")
    user_data = database.get_user(username)

    if not user_data:
        print("[DEBUG authenticate_user] Usuário NÃO encontrado no database.py.")
        return None
    else:
        print(f"[DEBUG authenticate_user] Usuário encontrado: {user_data.get('username')}")

    stored_hashed_password = user_data.get("hashed_password")
    print(f"[DEBUG authenticate_user] Hash armazenado: '{stored_hashed_password}'")
    print(f"[DEBUG authenticate_user] Verificando senha digitada ('{password}') contra o hash...")

    is_password_correct = security.verify_password(password, stored_hashed_password)

    if not is_password_correct:
        print("[DEBUG authenticate_user] Verificação de senha: INCORRETA.")
        return None
    else:
        print("[DEBUG authenticate_user] Verificação de senha: CORRETA.")
        return User(**user_data)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Cria um novo token de acesso (JWT).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# --- Endpoint de Login ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Recebe username e password de um formulário e retorna um JWT.
    """
    # ================== DEBUG PONTO 1: VERIFICAR DADOS RECEBIDOS ==================
    print("\n--- [DEBUG /token] Tentativa de Login Recebida ---")
    print(f"Username recebido: '{form_data.username}'")
    print(f"Password recebido: '{form_data.password}'")
    # ===========================================================================

    user = authenticate_user(form_data.username, form_data.password)

    # ================== DEBUG PONTO 3: VERIFICAR RESULTADO DA AUTENTICAÇÃO ==================
    if not user:
        print("--- [DEBUG /token] Resultado da Autenticação: FALHA (Usuário NÃO encontrado ou senha incorreta)")
        print("-" * 50 + "\n")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    else:
        print(f"--- [DEBUG /token] Resultado da Autenticação: SUCESSO (Usuário: {user.username})")
        print("-" * 50 + "\n")
    # ===================================================================================

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "tenant_id": user.tenant_id},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_active_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Decodifica o token JWT, valida o usuário e retorna seus dados.
    Esta é a nossa dependência de segurança ("o porteiro").
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Tenta decodificar o token usando nossa chave secreta
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # Busca o usuário no nosso "banco de dados"
    user_data = database.get_user(username=token_data.username)
    if user_data is None:
        raise credentials_exception

    user = User(**user_data)
    # Verifica se o usuário está desativado
    if user.disabled:
        raise HTTPException(status_code=400, detail="Usuário inativo")

    # Se tudo estiver OK, retorna os dados do usuário
    return user

async def get_current_user_for_websocket(token: Optional[str] = None) -> User:
    """Dependência para autenticar usuários em conexões WebSocket via token."""
    if token is None:
        raise WebSocketDisconnect(code=status.WS_1008_POLICY_VIOLATION)
    return await get_current_active_user(token)


@app.post("/conversations/{jid:path}/mark-read") # <--- VERIFIQUE ESTA LINHA
async def mark_conversation_as_read(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Marca uma conversa específica como lida (unread = False).
    """
    global CONVERSATION_STATE_STORE

    # Usa a busca inteligente para encontrar o JID correto
    conversation_to_update = find_existing_conversation_jid(jid)
    if not conversation_to_update:
        conversation_to_update = jid

    async with STATE_LOCK: # Protege a escrita no estado global
        if conversation_to_update in CONVERSATION_STATE_STORE:
                # Verifica se realmente precisa atualizar
                if CONVERSATION_STATE_STORE[conversation_to_update].get("unread", False):
                    CONVERSATION_STATE_STORE[conversation_to_update]["unread"] = False
                    CONVERSATION_STATE_STORE[conversation_to_update]["unreadCount"] = 0 # <-- RESETA A CONTAGEM
                    print(f"INFO: Conversa '{conversation_to_update}' marcada como LIDA. Contagem resetada.")
                    return {"status": "success", "message": "Conversation marked as read."}
                else:
                    # Se já estava lida, apenas garante que a contagem é 0
                    CONVERSATION_STATE_STORE[conversation_to_update]["unreadCount"] = 0
                    return {"status": "success", "message": "Conversation was already read."}
        else:
             print(f"AVISO: Tentativa de marcar como lida uma conversa não encontrada no estado: {conversation_to_update}")
             return {"status": "success", "message": "Conversation not found in current state, but proceeding."}
# ===================================================================
#           FIM DO CÓDIGO DO "PORTEIRO"
# ===================================================================

# --- GATILHO DE INICIALIZAÇÃO ---

@app.on_event("startup")
async def on_startup():
    # A sincronização agora roda como uma tarefa em segundo plano
    # para não bloquear a inicialização do servidor.
    asyncio.create_task(load_history_from_evolution_api())
# ... (o resto do seu código, como a configuração do CORS, continua aqui)
# Configuração de CORS

origins = ["http://localhost:3000"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def find_existing_conversation_jid(jid: str) -> str | None:
    """
    Busca por um JID no estado da conversa, considerando a variação do 9º dígito
    para números brasileiros. Retorna o JID correto se encontrado, senão None.
    """
    # 1. Tenta encontrar a correspondência exata primeiro (mais rápido)
    if jid in CONVERSATION_STATE_STORE:
        return jid

    # 2. Se não encontrou, e for um número brasileiro, tenta a variação
    # Remove o '@s.whatsapp.net' para trabalhar só com os números
    number_part = jid.split('@')[0]

    # Verifica se é um número brasileiro (começa com 55, tem DDD)
    if number_part.startswith('55') and len(number_part) > 4:
        ddi = number_part[:2]  # "55"
        ddd = number_part[2:4]  # "41"
        rest_of_number = number_part[4:]

        alternative_jid = None
        # Se o número tem o 9º dígito (ex: 98...), cria a versão sem ele
        if len(rest_of_number) == 9 and rest_of_number.startswith('9'):
            alternative_jid = f"{ddi}{ddd}{rest_of_number[1:]}@s.whatsapp.net"
        # Se o número NÃO tem o 9º dígito (ex: 8...), cria a versão com ele
        elif len(rest_of_number) == 8:
            alternative_jid = f"{ddi}{ddd}9{rest_of_number}@s.whatsapp.net"

        # 3. Verifica se a versão alternativa existe no nosso estado
        if alternative_jid and alternative_jid in CONVERSATION_STATE_STORE:
            print(f"  -> [INFO] JID alternativo encontrado: {jid} corresponde a {alternative_jid}")
            return alternative_jid

    # 4. Se nenhuma versão foi encontrada, retorna None
    return None

@app.get("/debug/{jid:path}")
async def debug_conversation_state(jid: str, current_user: User = Depends(get_current_active_user)):
    """
    Endpoint de depuração para inspecionar o estado de uma única conversa na memória.
    Use o JID completo, ex: 5541999999999@s.whatsapp.net
    """
    if jid in CONVERSATION_STATE_STORE:
        return CONVERSATION_STATE_STORE[jid]
    else:
        # Se não encontrar, tenta a variação com/sem o 9º dígito (bônus)
        alternative_jid = find_existing_conversation_jid(jid)
        if alternative_jid and alternative_jid in CONVERSATION_STATE_STORE:
            return CONVERSATION_STATE_STORE[alternative_jid]
        raise HTTPException(status_code=404, detail=f"JID {jid} não encontrado no estado da conversa.")

@app.get("/contacts/info/{number}")
async def get_contact_info(number: str, current_user: User = Depends(get_current_active_user)):
    """Busca nome e foto de um número na Evolution API para preview."""
    jid = f"{number}@s.whatsapp.net"
    try:
        url = f"{EVO_URL}/contact/info/{EVO_INSTANCE}"
        params = {"jid": jid}
        headers = {"apikey": EVO_TOKEN}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status() # Lança um erro se a resposta for 4xx ou 5xx
            data = response.json()
            pic_url = data.get("profilePictureUrl") or data.get("url") or ""
            return {
                "name": data.get("name") or data.get("pushname") or number,
                "avatar_url": pic_url
            }
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Contato não encontrado no WhatsApp.")
        else:
            raise HTTPException(status_code=e.response.status_code, detail=f"Erro da API: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Em main.py, substitua a função original (próximo à linha 140) por esta:

async def send_whatsapp_message(recipient_jid: str, message_text: str) -> bool:
    """Envia uma mensagem de texto para um JID específico usando a Evolution API v2.2.3"""
    if not all([EVO_URL, EVO_INSTANCE, EVO_TOKEN]):
        print("❌ ERRO CRÍTICO: Variáveis de ambiente da Evolution API não estão configuradas.")
        return False

    # Remove o sufixo @s.whatsapp.net se existir para enviar apenas o número
    number_only = recipient_jid.split('@')[0]

    url = f"{EVO_URL}/message/sendText/{EVO_INSTANCE}"
    headers = {
        'Content-Type': 'application/json',
        'apikey': EVO_TOKEN
    }

    # Payload correto para Evolution API v2.2.3
    payload = {
        "number": number_only,
        "text": message_text
    }

    try:
        async with httpx.AsyncClient() as client:
            # --- LOGS PARA DEBUG ---
            print("\n" + "="*25 + " NOVA MENSAGEM SAINDO " + "="*25)
            print(f"  -> Destino: {number_only}")
            print(f"  -> URL da API: {url}")
            print(f"  -> Payload enviado:\n{json.dumps(payload, indent=2)}")
            # --- FIM DOS LOGS ---

            response = await client.post(url, headers=headers, json=payload, timeout=20.0)

            # --- LOGS DA RESPOSTA ---
            print(f"  -> Resposta da API (Status): {response.status_code}")
            print(f"  -> Resposta da API (Corpo):\n{response.text}")
            print("="*72 + "\n")
            # --- FIM DOS LOGS ---

            response.raise_for_status()

            print(f"✅ Mensagem enviada com sucesso para {number_only}.")
            return True

    except httpx.HTTPStatusError as e:
        print(f"❌ ERRO HTTP ao enviar mensagem: {e.response.status_code}")
        print(f"   Corpo da resposta do erro: {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ ERRO GERAL ao enviar mensagem: {e}")
        import traceback
        traceback.print_exc()
        return False

@app.get("/")
def read_root():
    return {"status": "VENAI Backend is running!"}


print("INFO: Carregando modelos e playbook na inicialização do servidor...")


@app.post("/conversations/start_new")
async def start_new_conversation(request: NewConversationRequest):
    """
    Inicia uma nova conversa, envia a mensagem e cria o estado na aplicação.
    """
    recipient_jid = f"{request.recipient_number}@s.whatsapp.net"

    # 1. Envia a mensagem inicial para o cliente via API
    success = await send_whatsapp_message(
        recipient_jid=recipient_jid,
        message_text=request.initial_message
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar a mensagem inicial pela API da Evolution.")

    # 2. Se o envio foi bem-sucedido, cria ou atualiza a conversa em nosso estado local
    print(f"  -> Registrando nova conversa iniciada pelo vendedor para {recipient_jid}")

    # Monta o objeto da primeira mensagem (enviada pelo vendedor)
    message_obj = {
        "content": request.initial_message,
        "sender": "vendedor",
        "timestamp": int(time.time()),
        "message_id": f"seller_init_{uuid.uuid4()}"
    }

    # Se a conversa já existir (caso raro), apenas adiciona a mensagem.
    # Se não, cria a estrutura completa.
    if recipient_jid not in CONVERSATION_STATE_STORE:
        CONVERSATION_STATE_STORE[recipient_jid] = {
            "name": recipient_jid.split('@')[0],  # Nome temporário
            "avatar_url": "",  # Foto vazia
            "messages": [message_obj],  # Adiciona a primeira mensagem
            "suggestions": [],
            "stage_id": "stage_prospecting"
        }
    else:
        CONVERSATION_STATE_STORE[recipient_jid]["messages"].append(message_obj)

    return {"status": "success", "message": "Conversa iniciada e registrada com sucesso."}

@app.get("/contacts/info/{number}")
async def get_contact_info(number: str):
    """Busca nome e foto de um número no WhatsApp."""
    jid = f"{number}@s.whatsapp.net"

    # Reutiliza as funções que já tínhamos!
    contact_name = await get_contact_name(jid)
    profile_pic = await get_profile_pic_url(jid)

    # Se o nome ainda for o número, significa que não foi encontrado
    if contact_name == number:
        raise HTTPException(status_code=404, detail="Contato não encontrado no WhatsApp.")

    return {"name": contact_name, "avatar_url": profile_pic}


@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str, token: str):
    # Autentica o usuário usando o token passado na URL
    user = await get_current_user_for_websocket(token)
    print(f"INFO: Usuário '{user.username}' autenticado para WebSocket na conversa {conversation_id}")

    await manager.connect(websocket, conversation_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(conversation_id)

# Carrega todos os modelos e o playbook.

llm, ensemble_retriever, embeddings_model, playbook = cerebro_ia.load_models()

print("✅ Modelos e playbook carregados. Servidor pronto.")
# --- Armazenamento Temporário de Conversas e Sugestões (Estado Global) ---


CONVERSATION_STATE_STORE: Dict[str, Any] = {}


async def get_contact_name(jid: str) -> str:
    """Busca o nome de um contato na Evolution API."""
    default_name = jid.split('@')[0]  # Usa o número como nome padrão
    try:
        url = f"{EVO_URL}/contact/info/{EVO_INSTANCE}"
        params = {"jid": jid}
        headers = {"apikey": EVO_TOKEN}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                # O nome pode estar em 'name' ou 'pushname'
                return data.get("name") or data.get("pushname") or default_name
            else:
                print(f"AVISO: Não foi possível obter o nome para {jid}. Usando nome padrão.")
                return default_name
    except Exception as e:
        print(f"ERRO ao buscar nome do contato para {jid}: {e}")
        return default_name


async def get_profile_pic_url(jid: str) -> str:
    """Busca a URL da foto de perfil de um contato na Evolution API."""
    default_pic = default_pic = f"https://i.pravatar.cc/150?u={jid}"
    try:
        url = f"{EVO_URL}/contact/profile-pic/{EVO_INSTANCE}"
        params = {"jid": jid}
        headers = {"apikey": EVO_TOKEN} # Usando a variável de ambiente correta
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            if response.status_code == 200:
                return response.json().get("url", default_pic)
            return default_pic
    except Exception as e:
        print(f"AVISO: Não foi possível obter a foto de perfil para {jid}: {e}")
        return default_pic


async def process_and_broadcast_message(conversation_id: str, message_obj: Dict[str, Any]):
    """
    Processa a mensagem, atualiza o estado (marcando como não lida) e extrai dados do cliente.
    """
    global CONVERSATION_STATE_STORE

    try:
        # --- ETAPA 1: Atualizar o estado global ---
        print(f"  -> Atualizando estado para {conversation_id}...")

        async with STATE_LOCK:  # Garante acesso seguro ao estado
            # Garante que a conversa exista na memória
            if conversation_id not in CONVERSATION_STATE_STORE:
                CONVERSATION_STATE_STORE[conversation_id] = {
                    "name": conversation_id.split('@')[0], "messages": [], "stage_id": playbook["initial_stage"],
                    "suggestions": [], "dados_cliente": {}, "unread": False, "unreadCount": 0, "lastUpdated": 0
                }
                # Garante que unreadCount exista se a conversa já existia antes
            if "unreadCount" not in CONVERSATION_STATE_STORE[conversation_id]:
                CONVERSATION_STATE_STORE[conversation_id]["unreadCount"] = 0

                # Adiciona a mensagem e atualiza o timestamp
            CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)
            CONVERSATION_STATE_STORE[conversation_id]["lastUpdated"] = message_obj.get("timestamp",
                                                                                       int(time.time())) * 1000

            # Marca como não lida e incrementa a contagem SE for do cliente
            if message_obj.get("sender") == "cliente":
                CONVERSATION_STATE_STORE[conversation_id]["unread"] = True
                CONVERSATION_STATE_STORE[conversation_id]["unreadCount"] += 1  # <-- INCREMENTA A CONTAGEM
                print(
                    f"  -> Conversa '{conversation_id}' marcada como NÃO LIDA. Contagem: {CONVERSATION_STATE_STORE[conversation_id]['unreadCount']}.")
            else:
                # Se for do vendedor, apenas garante que está marcada como lida (se necessário)
                # CONVERSATION_STATE_STORE[conversation_id]["unread"] = False # Opcional: marcar como lida qdo vendedor envia?
                print(f"  -> Mensagem do vendedor processada para '{conversation_id}'.")

    except Exception as e:
        import traceback
        print(f"❌ ERRO na tarefa em background 'process_and_broadcast_message': {e}")
        traceback.print_exc()

# Novo Endpoint para o frontend disparar o envio da resposta do vendedor


@app.post("/send_seller_message")
async def send_seller_message_route(request: MessageSendRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_active_user)):
    global CONVERSATION_STATE_STORE

    # 1. Envia mensagem via API Evolution
    success = await send_whatsapp_message(
        recipient_jid=request.conversation_id,
        message_text=request.message_text
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar mensagem via Evolution API.")

    # 2. Adiciona a mensagem do vendedor ao RAG e ao estado global em background (para aparecer no polling)
    def index_and_update_seller_message():
        message_obj = {
            "content": request.message_text,
            "sender": "vendedor",
            "timestamp": int(time.time()),
            "message_id": f"seller_send_{int(time.time())}"
        }

        # Indexar no RAG
        conversation_db = cerebro_ia.get_or_create_conversation_db(request.conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(conversation_db, request.conversation_id, message_obj)

        # Atualizar o estado global
        if request.conversation_id in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[request.conversation_id]["messages"].append(message_obj)
            # Limpa as sugestões após o vendedor responder
            CONVERSATION_STATE_STORE[request.conversation_id]["suggestions"] = []

    background_tasks.add_task(index_and_update_seller_message)

    return {"status": "success", "message": "Mensagem enviada e indexada para polling."}


@app.get("/conversations")
async def get_all_conversations(current_user: User = Depends(get_current_active_user)):
    """
    Endpoint PROTEGIDO para buscar todas as conversas.
    Só pode ser acessado com um token JWT válido.
    """
    print(f"INFO: Usuário '{current_user.username}' do tenant '{current_user.tenant_id}' acessou as conversas.")

    # O resto da sua lógica continua igual, mas agora dentro de um endpoint seguro.
    formatted_conversations = []
    async with STATE_LOCK:
        store_copy = copy.deepcopy(CONVERSATION_STATE_STORE)

    for cid, data in store_copy.items():
        # Pega a última mensagem para fallback de lastUpdated
        last_msg_ts = data.get("messages", [{}])[-1].get("timestamp", 0) * 1000

        formatted_conversations.append({
            "id": cid,
            "name": data.get("name"),
            "avatar_url": data.get("avatar_url"),
            "messages": data.get("messages", []),
            "unread": data.get("unread", False),  # <-- GARANTIR QUE ESTÁ AQUI
            "unreadCount": data.get("unreadCount", 0),  # <-- ADICIONE/CONFIRME ESTA LINHA
            "lastUpdated": data.get("lastUpdated", last_msg_ts),  # <-- GARANTIR QUE ESTÁ AQUI
            "stage_id": data.get("stage_id"),
            # Adicionamos dados_cliente aqui também, pode ser útil no futuro
            "dados_cliente": data.get("dados_cliente", {}),
        })
    return {"status": "success", "conversations": formatted_conversations}


@app.post("/generate_response")
async def generate_response(request: SuggestionRequest, current_user: User = Depends(get_current_active_user)):
    """Gera sugestões de venda usando a memória estruturada e o RAG dinâmico."""
    try:
        # 1. Pega os dados completos da conversa do nosso estado em memória
        conversation_data = CONVERSATION_STATE_STORE.get(request.conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")

        full_history = conversation_data.get("messages", [])
        client_data = conversation_data.get("dados_cliente", {})  # <-- PEGA OS DADOS DO CLIENTE

        # 2. Chama a função do cérebro passando todos os contextos
        resultado_ia = cerebro_ia.generate_sales_suggestions(
            llm=llm,
            ensemble_retriever=ensemble_retriever,
            embeddings_model=embeddings_model,
            playbook=playbook,
            query=request.query,
            conversation_id=request.conversation_id,
            current_stage_id=request.current_stage_id,
            full_conversation_history=full_history,
            client_data=client_data,
            is_private_query=request.is_private_query
        )
        return resultado_ia

    except Exception as e:
        import traceback
        print(f"❌ ERRO CRÍTICO em /generate_response: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
async def create_or_update_conversation_details(contact_id: str, contact_data: dict):
    """Cria uma nova conversa se não existir, ou atualiza nome e foto se já existir."""
    if contact_id not in CONVERSATION_STATE_STORE:
        # Se a conversa não existe, cria com os dados que temos
        CONVERSATION_STATE_STORE[contact_id] = {
            "name": contact_data.get("pushName") or contact_id.split('@')[0],
            "avatar_url": contact_data.get("profilePictureUrl") or "",
            "messages": [],
            "suggestions": [],
            "stage_id": "stage_prospecting"
        }
        print(f"  -> [INFO] Nova conversa criada para {contact_id} a partir de dados de contato.")
    else:
        # Se a conversa já existe, apenas atualiza os detalhes
        new_name = contact_data.get("pushName")
        if new_name:
            CONVERSATION_STATE_STORE[contact_id]["name"] = new_name
        new_pic_url = contact_data.get("profilePictureUrl")
        if new_pic_url:
            CONVERSATION_STATE_STORE[contact_id]["avatar_url"] = new_pic_url
        print(f"  -> [INFO] Detalhes da conversa {contact_id} atualizados.")


# Em main.py, substitua a função inteira por esta versão

async def load_history_from_evolution_api():

    async with STATE_LOCK:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {"apikey": EVO_TOKEN, "Content-Type": "application/json"}

                # PASSO 1: Buscar Contatos
                contacts_url = f"{EVO_URL}/chat/findContacts/{EVO_INSTANCE}"
                contacts_response = await client.post(contacts_url, headers=headers, json={})
                contacts_response.raise_for_status()
                contacts = contacts_response.json() or []
                print_success(f"✅ Encontrados {len(contacts)} contatos.")

                # PASSO 2: Carregar Histórico Completo
                all_messages_flat_list = []
                current_page, total_pages = 1, 1
                while current_page <= total_pages:
                    messages_url = f"{EVO_URL}/chat/findMessages/{EVO_INSTANCE}"
                    payload = {"limit": 100, "page": current_page}
                    response = await client.post(messages_url, headers=headers, json=payload, timeout=60.0)
                    if response.status_code != 200: break
                    data = response.json()
                    message_data = data.get("messages", {})
                    total_pages = message_data.get("pages", 1)
                    records = message_data.get("records", [])
                    if not records: break
                    all_messages_flat_list.extend(records)
                    print(f"    - Página {current_page}/{total_pages} carregada...")
                    current_page += 1
                print_success(f"✅ Histórico de {len(all_messages_flat_list)} mensagens carregado.")

                # PASSO 3: Agrupar mensagens e montar o estado final
                messages_grouped_by_jid = {}
                for msg in all_messages_flat_list:
                    key = msg.get("key", {})
                    remote_jid = key.get("remoteJid")
                    if not remote_jid: continue
                    if remote_jid not in messages_grouped_by_jid:
                        messages_grouped_by_jid[remote_jid] = []
                    message_obj = msg.get("message", {})
                    content = message_obj.get("conversation") or message_obj.get("extendedTextMessage", {}).get("text")
                    if content:
                        messages_grouped_by_jid[remote_jid].append({
                            "content": content,
                            "sender": "vendedor" if key.get("fromMe") else "cliente",
                            "timestamp": msg.get("messageTimestamp", int(time.time())),
                            "message_id": key.get("id", str(uuid.uuid4()))
                        })

                new_conversation_store: Dict[str, Any] = {}
                conversations_added = 0  # Contador para o log
                for contact in contacts:
                    jid = contact.get("remoteJid")
                    if not jid or "@s.whatsapp.net" not in jid or "@g.us" in jid:
                        continue

                    # Pega a lista de mensagens que agrupamos para este JID (ou uma lista vazia).
                    contact_messages = messages_grouped_by_jid.get(jid, [])

                    # =====================================================================
                    # A NOVA CONDIÇÃO ESTÁ AQUI:
                    # Só adiciona a conversa ao estado se ela tiver mensagens.
                    # =====================================================================
                    if contact_messages:
                        contact_messages.sort(key=lambda x: x["timestamp"])  # Ordena só se houver mensagens
                        name = contact.get("pushName") or contact.get("name") or jid.split('@')[0]

                        new_conversation_store[jid] = {
                            "name": name,
                            "avatar_url": contact.get("profilePicUrl") or "",
                            "messages": contact_messages,
                            "suggestions": [],
                            "dados_cliente": {},
                            "unread": False,
                            "unreadCount": 0,
                            "stage_id": "stage_prospecting"
                        }
                        conversations_added += 1  # Incrementa o contador
                    # =====================================================================

                global CONVERSATION_STATE_STORE
                CONVERSATION_STATE_STORE = copy.deepcopy(new_conversation_store)

                print_success("\n" + "=" * 70)
                print_success("SINCRONIZAÇÃO PARA FRONTEND CONCLUÍDA COM SUCESSO!")
                # Atualiza o log para mostrar o número real de conversas montadas
                print_info(f"📊 Resumo: {conversations_added} conversas com mensagens montadas.")
                print_info("=" * 70 + "\n")

        except Exception as e:
            print_error(f"\n❌ ERRO CRÍTICO na sincronização: {e}")
            import traceback
            traceback.print_exc()

@app.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    raw_body = await request.body()
    if not raw_body: return {"status": "ignored_empty_body"}

    try:
        body = json.loads(raw_body)
        event_type = body.get("event")
        data = body.get("data", {})
        if isinstance(data, list): data = data[0] if data else {}

        # --- LÓGICA UNIFICADA PARA ATUALIZAR/CRIAR CONVERSA ---

        # 1. Determina o JID (ID da conversa) com base no tipo de evento
        jid = None
        if event_type in ["contacts.update", "contacts.upsert"]:
            jid = data.get("id")
        elif event_type == "messages.upsert":
            jid = data.get("key", {}).get("remoteJid")

        if not jid:
            return {"status": "event_ignored_no_jid"}

        # 2. Usa a busca inteligente para encontrar a conversa, mesmo com variação do 9º dígito
        existing_jid = find_existing_conversation_jid(jid)
        conversation_to_update = existing_jid or jid

        # 3. Se a conversa ainda não existe, cria uma estrutura básica
        if conversation_to_update not in CONVERSATION_STATE_STORE:
            print(f"  -> Criando nova conversa para {conversation_to_update}.")
            CONVERSATION_STATE_STORE[conversation_to_update] = {
                "name": conversation_to_update.split('@')[0], "avatar_url": "",
                "messages": [], "suggestions": [], "stage_id": "stage_prospecting"
            }

        # 4. ATUALIZA os detalhes com a informação mais recente que tivermos, de QUALQUER evento
        # Se o evento trouxer um nome, atualiza.
        if data.get("pushName"):
            CONVERSATION_STATE_STORE[conversation_to_update]["name"] = data.get("pushName")
        # Se o evento trouxer uma foto, atualiza.
        if data.get("profilePictureUrl"):
            CONVERSATION_STATE_STORE[conversation_to_update]["avatar_url"] = data.get("profilePictureUrl")

        # 5. Se o evento for uma mensagem, agenda o salvamento dela
        if event_type == "messages.upsert" and not data.get("key", {}).get("fromMe"):
            message_content = (data.get("message", {}).get("conversation") or data.get("message", {}).get(
                "extendedTextMessage", {}).get("text"))
            if message_content:
                message_obj = {"content": message_content, "sender": "cliente",
                               "timestamp": data.get("messageTimestamp"), "message_id": data.get("key", {}).get("id")}

                background_tasks.add_task(process_and_broadcast_message, conversation_to_update, message_obj)

    except Exception as e:
        print(f"❌ ERRO CRÍTICO no webhook: {e}")

    return {"status": "event_processed"}

@app.post("/conversations/start_new")
async def start_new_conversation(request: NewConversationRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_active_user)):
    """
    Inicia uma nova conversa enviando uma mensagem inicial para um novo contato.
    """
    # Formata o JID (ID do WhatsApp)
    recipient_jid = f"{request.recipient_number}@s.whatsapp.net"

    # 1. Tenta enviar a mensagem inicial
    success = await send_whatsapp_message(
        recipient_jid=recipient_jid,
        message_text=request.initial_message
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar a mensagem inicial. Verifique o número e a conexão com a API.")

    # 2. Se o envio for bem-sucedido, adiciona a mensagem ao nosso estado interno
    #    para que ela apareça imediatamente no frontend (via polling).
    #    Usamos uma tarefa em segundo plano para não bloquear a resposta.
    message_obj = {
        "content": request.initial_message,
        "sender": "vendedor",
        "timestamp": int(time.time()),
        "message_id": f"seller_init_{int(time.time())}"
    }

    # Agenda a criação da conversa e o salvamento da mensagem
    background_tasks.add_task(
        process_and_broadcast_message,
        recipient_jid,
        message_obj,
    )

    return {"status": "success", "message": "Conversa iniciada. A mensagem aparecerá em breve."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)