import os, time, httpx, uuid, json, uvicorn, asyncio, copy
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any

from core import cerebro_ia

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

app = FastAPI()
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
async def debug_conversation_state(jid: str):
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
async def get_contact_info(number: str):
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
    return {"status": "Cosmos Copilot Backend is running!"}


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
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    await manager.connect(websocket, conversation_id)
    try:
        while True:
            data = await websocket.receive_text()
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
    Processa a mensagem, atualiza o estado, salva no RAG e extrai dados do cliente.
    """
    global CONVERSATION_STATE_STORE

    try:
        # --- ETAPA 1: Atualizar o estado global para o polling do Frontend ---
        print(f"  -> Atualizando estado global para a interface do usuário...")
        # Garante que a conversa exista na memória
        if conversation_id not in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[conversation_id] = {
                "name": conversation_id.split('@')[0],
                "messages": [],
                "stage_id": playbook["initial_stage"],
                "suggestions": [],
                "dados_cliente": {}
            }

        # Adiciona a nova mensagem à lista
        CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)
        print(f"  -> Estado global atualizado com sucesso.")

        # --- ETAPA 2: Salvar no RAG para a memória de longo prazo da IA ---
        # print(f"  -> Salvando mensagem de '{conversation_id}' na memória RAG (Cérebro 2)...")
        # db_conversa = cerebro_ia.get_or_create_conversation_db(conversation_id, embeddings_model)
        # cerebro_ia.add_message_to_conversation_rag(db_conversa, conversation_id, message_obj)
        # print(f"  -> Mensagem salva no RAG com sucesso.")
        # NOTA: O salvamento no RAG persistente está desativado conforme nossa conversa anterior.

        # --- ETAPA 3 (NOVA): Extrair e atualizar os dados do cliente ---
        # Só executamos essa etapa custosa se a mensagem for do cliente
        if message_obj.get("sender") == "cliente":
            # Pega o histórico completo e atualizado
            full_history = CONVERSATION_STATE_STORE[conversation_id].get("messages", [])

            # Formata o histórico para uma string simples que a IA entende
            history_text = "\n".join([f"{msg['sender'].capitalize()}: {msg['content']}" for msg in full_history])

            # Chama nosso "Mini-Cérebro" extrator
            extracted_data = cerebro_ia.extract_client_data_from_history(llm, history_text)

            # Pega os dados que já tínhamos...
            current_client_data = CONVERSATION_STATE_STORE[conversation_id].get("dados_cliente", {})
            # ...e os novos dados extraídos (ignorando campos nulos)...
            new_client_data = extracted_data.dict(exclude_unset=True)

            # ...e faz o merge, atualizando a "ficha do cliente".
            current_client_data.update(new_client_data)
            CONVERSATION_STATE_STORE[conversation_id]["dados_cliente"] = current_client_data
            print(f"  -> 'Arquivo do Cliente' atualizado: {current_client_data}")

    except Exception as e:
        import traceback
        print(f"❌ ERRO na tarefa em background 'process_and_broadcast_message': {e}")
        traceback.print_exc()

# Novo Endpoint para o frontend disparar o envio da resposta do vendedor


@app.post("/send_seller_message")
async def send_seller_message_route(request: MessageSendRequest, background_tasks: BackgroundTasks):
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
async def get_all_conversations():
    formatted_conversations = []
    # Adquirimos a trava antes de LER o estado.
    # Isso garante que não vamos ler um estado pela metade enquanto a sincronização está rodando.
    async with STATE_LOCK:
        # Usamos copy.deepcopy para enviar uma cópia, não a referência original,
        # para o frontend. Mais seguro.
        store_copy = copy.deepcopy(CONVERSATION_STATE_STORE)

    for cid, data in store_copy.items():
        formatted_conversations.append({
            "id": cid,
            "name": data.get("name"),
            "avatar_url": data.get("avatar_url"),
            "messages": data.get("messages", []),
            "stage_id": data.get("stage_id"),
        })
    return {"status": "success", "conversations": formatted_conversations}


@app.post("/generate_response")
async def generate_response(request: SuggestionRequest):
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
    """
    VERSÃO ATUALIZADA (V9.1): Cria a estrutura 'dados_cliente' para cada conversa.
    """
    print_info("\n" + "=" * 70)
    print_info("INICIANDO SINCRONIZAÇÃO (V9.1 - CRIANDO ARQUIVO DO CLIENTE)")
    print_info("=" * 70)

    async with STATE_LOCK:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                headers = {"apikey": EVO_TOKEN, "Content-Type": "application/json"}

                # PASSO 1: Buscar Contatos
                print_info("\n[1/3] Buscando lista de contatos...")
                contacts_url = f"{EVO_URL}/chat/findContacts/{EVO_INSTANCE}"
                contacts_response = await client.post(contacts_url, headers=headers, json={})
                contacts_response.raise_for_status()
                contacts = contacts_response.json() or []
                print_success(f"✅ Encontrados {len(contacts)} contatos.")

                # PASSO 2: Carregar Histórico Completo
                print_info("\n[2/3] Carregando todo o histórico de mensagens...")
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
                print_info("\n[3/3] Montando estado para o frontend...")
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
                for contact in contacts:
                    jid = contact.get("remoteJid")
                    if not jid or "@s.whatsapp.net" not in jid or "@g.us" in jid:
                        continue
                    contact_messages = messages_grouped_by_jid.get(jid, [])
                    contact_messages.sort(key=lambda x: x["timestamp"])
                    name = contact.get("pushName") or contact.get("name") or jid.split('@')[0]

                    # --- AQUI ESTÁ A MUDANÇA ---
                    new_conversation_store[jid] = {
                        "name": name,
                        "avatar_url": contact.get("profilePicUrl") or "",
                        "messages": contact_messages,
                        "suggestions": [],
                        "dados_cliente": {},  # Cria o campo para os dados estruturados
                        "stage_id": "stage_prospecting"
                    }
                    # --------------------------

                global CONVERSATION_STATE_STORE
                CONVERSATION_STATE_STORE = copy.deepcopy(new_conversation_store)

                print_success("\n" + "=" * 70)
                print_success("SINCRONIZAÇÃO PARA FRONTEND CONCLUÍDA COM SUCESSO!")
                print_info(f"📊 Resumo: {len(new_conversation_store)} conversas montadas.")
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
async def start_new_conversation(request: NewConversationRequest, background_tasks: BackgroundTasks):
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