import os, time, httpx, uuid, json, uvicorn

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any

from core import cerebro_ia


# --- Gerenciador de Conexões WebSocket (Inalterado) ---
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


manager = ConnectionManager()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

EVO_URL = os.getenv("EVOLUTION_API_URL")
EVO_INSTANCE = os.getenv("EVOLUTION_INSTANCE_NAME")
EVO_KEY = os.getenv("EVOLUTION_API_KEY")

# --- 1. Inicialização da Aplicação e Carregamento dos Modelos ---

app = FastAPI()

# Configuração de CORS
origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"status": "Cosmos Copilot Backend is running!"}


print("INFO: Carregando modelos e playbook na inicialização do servidor...")


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


class MessageSendRequest(BaseModel):
    conversation_id: str
    message_text: str


# Função para enviar a mensagem via API Evolution (Inalterada)
async def send_whatsapp_message(recipient_jid: str, message_text: str):
    if not all([EVO_URL, EVO_INSTANCE, EVO_KEY]):
        print("❌ ERRO: Configuração da Evolution API faltando.")
        return False

    url = f"{EVO_URL}/message/sendText/{EVO_INSTANCE}"
    headers = {'Content-Type': 'application/json', 'apikey': EVO_KEY}
    payload = {"number": recipient_jid.split('@')[0], "textMessage": {"text": message_text}}

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


# --- FUNÇÃO CORRIGIDA PARA ATUALIZAR O ESTADO GLOBAL (Polling) ---
async def process_and_broadcast_message(conversation_id: str, message_obj: Dict[str, Any]):
    global CONVERSATION_STATE_STORE  # <--- ESSENCIAL para acesso ao estado

    try:
        # 1. Salva a mensagem na memória (RAG Conversacional)
        print(f"  -> Salvando mensagem de '{conversation_id}' na memória RAG...")
        db = cerebro_ia.get_or_create_conversation_db(conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(db, conversation_id, message_obj)

        # 2. Atualiza o Estado Global para o Polling do Frontend
        print(f"  -> Salvando mensagem de '{conversation_id}' no estado global...")
        if conversation_id not in CONVERSATION_STATE_STORE:
            CONVERSATION_STATE_STORE[conversation_id] = {
                "id": conversation_id,
                "name": conversation_id.split('@')[0],
                "messages": [],  # Inicializa a lista de mensagens
                "stage_id": playbook["initial_stage"],
                "suggestions": []
            }

        # Adiciona a mensagem e atualiza o estado
        CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)
        print(f"  -> Mensagem salva com sucesso no estado global para polling.")

    except Exception as e:
        print(f"❌ ERRO na tarefa em background 'process_and_broadcast_message': {e}")


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


# --- Definição dos Modelos de Dados (Pydantic) ---
class SuggestionRequest(BaseModel):
    query: str
    conversation_id: str
    current_stage_id: str | None = Field(default=None)


# --- Endpoints da API ---
@app.get("/conversations")
async def get_all_conversations():
    """Endpoint para o frontend buscar todas as conversas e sugestões atualizadas."""
    global CONVERSATION_STATE_STORE

    # Retorna todas as conversas salvas no estado global
    return {"status": "success", "conversations": list(CONVERSATION_STATE_STORE.values())}


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


# --- ENDPOINT FINAL CORRIGIDO PARA RECEBER WEBHOOKS ---
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
            if not isinstance(message_data, dict):
                print(f"  -> AVISO: Dado inesperado no webhook (não é um dicionário). Pulando.")
                continue

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
                "message_id": message_data.get("key", {}).get("id") or str(uuid.uuid4())
            }

            # 4. Adiciona a tarefa CORRETA ao background.
            background_tasks.add_task(
                process_and_broadcast_message,
                conversation_id,
                message_obj,
            )

    except Exception as e:
        print(f"❌ ERRO CRÍTICO ao processar webhook 'messages.upsert': {e}")
        return {"status": "error_during_processing", "detail": str(e)}


    return {"status": "received_and_queued_for_processing"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)