import os, time, httpx, uuid, json, uvicorn

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any

from core import cerebro_ia

class ConnectionManager:
    def __init__(self):
        # Dicionário para armazenar as conexões ativas.
        # A chave será o conversation_id e o valor será o objeto WebSocket.
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        # Aceita uma nova conexão.
        await websocket.accept()
        # Armazena a conexão associada ao ID da conversa.
        self.active_connections[conversation_id] = websocket
        print(f"INFO: WebSocket conectado para a conversa {conversation_id}")

    def disconnect(self, conversation_id: str):
        # Remove uma conexão quando o cliente se desconecta.
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
            print(f"INFO: WebSocket desconectado da conversa {conversation_id}")

    async def send_personal_message(self, message: str, conversation_id: str):
        # Envia uma mensagem para um cliente específico.
        if conversation_id in self.active_connections:
            websocket = self.active_connections[conversation_id]
            await websocket.send_text(message)

# Cria uma instância global do nosso gerenciador.
manager = ConnectionManager()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_KEY = os.getenv("EVOLUTION_API_KEY")

# --- 1. Inicialização da Aplicação e Carregamento dos Modelos ---

app = FastAPI()

# ==============================================================================
# MUDANÇA AQUI: Adicionamos a configuração de CORS
# ==============================================================================

# Define de quais origens (endereços) o backend aceitará requisições.
origins = [
    "http://localhost:3000", # Endereço padrão do React em desenvolvimento
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Lista de origens permitidas
    allow_credentials=True,      # Permite cookies (não usamos, mas é boa prática)
    allow_methods=["*"],         # Permite todos os métodos (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],         # Permite todos os cabeçalhos
)
# ==============================================================================

@app.get("/")
def read_root():
    return {"status": "Cosmos Copilot Backend is running!"}

print("INFO: Carregando modelos e playbook na inicialização do servidor...")

@app.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    # Registra a nova conexão no nosso gerenciador.
    await manager.connect(websocket, conversation_id)
    try:
        # Mantém a conexão viva em um loop infinito.
        while True:
            # Apenas aguarda o cliente enviar alguma mensagem (não faremos nada com ela por enquanto).
            # Se o cliente desconectar, esta linha vai gerar uma exceção.
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        # Quando a exceção de desconexão acontece, removemos o cliente do gerenciador.
        manager.disconnect(conversation_id)

llm, ensemble_retriever, embeddings_model, playbook = cerebro_ia.load_models()

print("✅ Modelos e playbook carregados. Servidor pronto.")

# --- NOVO: Armazenamento Temporário de Conversas e Sugestões ---
CONVERSATION_STATE_STORE: Dict[str, Any] = {}

class MessageSendRequest(BaseModel):
    conversation_id: str
    message_text: str

# Função para enviar a mensagem via API Evolution
async def send_whatsapp_message(recipient_jid: str, message_text: str):
    if not all([EVO_URL, EVO_INSTANCE, EVO_KEY]):
        print("❌ ERRO: Configuração da Evolution API faltando.")
        return False

    url = f"{EVO_URL}/message/sendText/{EVO_INSTANCE}"

    headers = {
        'Content-Type': 'application/json',
        'apikey': EVO_KEY # Ou 'api-key', dependendo da sua versão
    }

    payload = {
        "number": recipient_jid.split('@')[0], # Retira o @s.whatsapp.net
        "textMessage": { "text": message_text }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=20)
            response.raise_for_status()
            print(f"✅ Mensagem enviada para {recipient_jid}.")
            return True
    except httpx.HTTPStatusError as e:
        print(f"❌ ERRO HTTP ao enviar mensagem: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        print(f"❌ ERRO ao enviar mensagem para Evolution: {e}")
        return False

# Novo Endpoint para o frontend disparar o envio da resposta do vendedor
@app.post("/send_seller_message")
async def send_seller_message_route(request: MessageSendRequest, background_tasks: BackgroundTasks):
    global CONVERSATION_STATE_STORE

    success = await send_whatsapp_message(
        recipient_jid=request.conversation_id,
        message_text=request.message_text
    )

    if not success:
        raise HTTPException(status_code=500, detail="Falha ao enviar mensagem via Evolution API.")

    # Adiciona a mensagem do vendedor ao RAG e ao estado global em background (para aparecer no polling)
    def index_and_update_seller_message():
        message_obj = {
            "content": request.message_text,
            "sender": "vendedor",
            "timestamp": int(time.time()),
            "message_id": f"seller_send_{int(time.time())}"
        }

        # 1. Indexar no RAG (para o Copilot ter o contexto)
        conversation_db = cerebro_ia.get_or_create_conversation_db(request.conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(conversation_db, request.conversation_id, message_obj)

        # 2. Atualizar o estado global (para o frontend buscar via polling)
        if request.conversation_id in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[request.conversation_id]["messages"].append(message_obj)
            # Limpa as sugestões após o vendedor responder
            CONVERSATION_STATE_STORE[request.conversation_id]["suggestions"] = []

    background_tasks.add_task(index_and_update_seller_message)

    return {"status": "success", "message": "Mensagem enviada e indexada para polling."}



# --- 2. Definição dos Modelos de Dados (Pydantic) ---
# ... (sem alterações aqui)
class SuggestionRequest(BaseModel):
    query: str
    conversation_id: str
    current_stage_id: str | None = Field(default=None)

# ... (seu modelo EvolutionPayload permanece o mesmo)


# --- 3. Endpoints da API ---
# ... (seus endpoints @app.post permanecem os mesmos)
@app.get("/conversations")
async def get_all_conversations():
    """Endpoint para o frontend buscar todas as conversas e sugestões atualizadas."""
    global CONVERSATION_STATE_STORE

    # Retorna todas as conversas salvas no estado global
    # O frontend espera uma estrutura específica com a chave 'conversations'
    return {"status": "success", "conversations": list(CONVERSATION_STATE_STORE.values())}

# CÓDIGO COMPLETO (com as outras partes inalteradas para facilitar)

@app.post("/generate_response")
async def generate_response(request: SuggestionRequest):
    try:
        suggestion_response = cerebro_ia.generate_sales_suggestions(
            llm=llm,
            ensemble_retriever=ensemble_retriever,
            embeddings_model=embeddings_model,
            playbook=playbook,
            query=request.query,
            conversation_id=request.conversation_id,
            current_stage_id=request.current_stage_id
        )
        return suggestion_response
    except Exception as e:
        print(f"❌ ERRO CRÍTICO em /generate_response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Novo Endpoint para Webhook da Evolution API ---
# A Evolution API envia dados em um formato que precisa ser processado.
# Este é um modelo simplificado dos dados mais importantes:
class EvolutionWebhookEvent(BaseModel):
    event: str
    instance: str
    data: dict


# Certifique-se de que esta função esteja DENTRO do seu main.py,
# e que as variáveis globais (cerebro_ia, embeddings_model) estejam acessíveis.
@app.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()

    # 1. Filtra o evento logo no início para maior eficiência.
    if payload.get("event") != "messages.upsert":
        return {"status": "ignored_not_a_message_event"}

    print(f"INFO: Webhook 'messages.upsert' recebido da instância {payload.get('instance')}")

    TIME_LIMIT_SECONDS = 300  # 5 minutos
    current_timestamp = time.time()

    try:
        # 2. Itera em um único loop sobre a lista de mensagens em "data".
        for message_data in payload.get("data", []):

            # --- Sequência de filtros "Fail-Fast" ---

            # Ignora mensagens enviadas por nós mesmos
            if message_data.get("key", {}).get("fromMe"):
                continue

            # Ignora mensagens muito antigas
            message_timestamp = message_data.get("messageTimestamp", 0)
            if current_timestamp - message_timestamp > TIME_LIMIT_SECONDS:
                continue

            # Extrai o conteúdo (suporta texto normal e texto estendido)
            message_content = (
                    message_data.get("message", {}).get("conversation") or
                    message_data.get("message", {}).get("extendedTextMessage", {}).get("text")
            )
            conversation_id = message_data.get("key", {}).get("remoteJid")

            # Se não houver conteúdo de texto ou ID da conversa, pula para a próxima mensagem
            if not message_content or not conversation_id:
                continue

            print(f"  -> Nova mensagem válida de '{conversation_id}'. Conteúdo: '{message_content}'")

            # 3. Monta o objeto da mensagem com dados mais precisos.
            message_obj = {
                "content": message_content,
                "sender": "cliente",
                "timestamp": message_timestamp,  # Usa o timestamp original da mensagem
                "message_id": message_data.get("key", {}).get("id") or str(uuid.uuid4())  # Fallback mais robusto
            }

            # 4. Adiciona a tarefa ao background para responder rapidamente ao webhook.
            background_tasks.add_task(
                full_webhook_processing_task,
                conversation_id,
                message_obj,
                message_content
            )

    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao processar webhook 'messages.upsert': {e}")
        # Retorna 200 para que a Evolution API não tente reenviar.
        return {"status": "error_during_processing", "detail": str(e)}

    # Resposta de sucesso imediata para a Evolution API.
    return {"status": "received_and_queued_for_processing"}

async def process_and_broadcast_message(conversation_id: str, message_obj: Dict[str, Any]):
    """
    Esta é a nossa nova tarefa em segundo plano. Ela faz duas coisas:
    1. Salva a nova mensagem na base de dados da conversa (Cérebro 2).
    2. Transmite a mesma mensagem via WebSocket para o frontend.
    """
    try:
        # 1. Salva a mensagem na memória (RAG Conversacional)
        print(f"  -> Salvando mensagem de '{conversation_id}' na memória...")
        db = cerebro_ia.get_or_create_conversation_db(conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(db, conversation_id, message_obj)
        print(f"  -> Mensagem salva com sucesso.")

        # 2. Transmite a mensagem para o frontend conectado
        print(f"  -> Transmitindo mensagem para o WebSocket de '{conversation_id}'...")
        # Converte o dicionário Python em uma string JSON para envio
        json_message = json.dumps(message_obj)
        await manager.send_personal_message(json_message, conversation_id)
        print(f"  -> Mensagem transmitida com sucesso.")

    except Exception as e:
        print(f"❌ ERRO na tarefa em background 'process_and_broadcast_message': {e}")

@app.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()

    if payload.get("event") != "messages.upsert":
        return {"status": "ignored_not_a_message_event"}

    print(f"INFO: Webhook 'messages.upsert' recebido da instância {payload.get('instance')}")

    TIME_LIMIT_SECONDS = 300
    current_timestamp = time.time()

    try:
        for message_data in payload.get("data", []):
            if message_data.get("key", {}).get("fromMe"):
                continue

            message_timestamp = message_data.get("messageTimestamp", 0)
            if current_timestamp - message_timestamp > TIME_LIMIT_SECONDS:
                continue

            message_content = (
                    message_data.get("message", {}).get("conversation") or
                    message_data.get("message", {}).get("extendedTextMessage", {}).get("text")
            )
            conversation_id = message_data.get("key", {}).get("remoteJid")

            if not message_content or not conversation_id:
                continue

            print(f"  -> Nova mensagem válida de '{conversation_id}'. Conteúdo: '{message_content}'")

            message_obj = {
                "content": message_content,
                "sender": "cliente",
                "timestamp": message_timestamp,
                "message_id": message_data.get("key", {}).get("id") or str(uuid.uuid4())  # O uuid agora funciona!
            }

            background_tasks.add_task(
                process_and_broadcast_message,  # <-- Nome da nova função
                conversation_id,
                message_obj,  # <-- Apenas os argumentos que a nova função precisa
            )

    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao processar webhook 'messages.upsert': {e}")
        return {"status": "error_during_processing", "detail": str(e)}

    return {"status": "received_and_queued_for_processing"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)