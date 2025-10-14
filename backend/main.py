import os
import time
import httpx
from dotenv import load_dotenv

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any

from core import cerebro_ia

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
llm, db_tecnico, embeddings_model, playbook = cerebro_ia.load_models()
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
            db_tecnico=db_tecnico,
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
@app.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    # NOTA: Usamos request.json() pois a Evolution API envia um corpo JSON no evento
    payload = await request.json()

    TIME_LIMIT_SECONDS = 300
    current_timestamp = time.time()  # Certifique-se de que time está importado (import time)

    for message_data in payload.get("data", {}).get("messages", []):

        message_timestamp = message_data.get("messageTimestamp", 0)

        # Se a mensagem for muito antiga, ignora.
        if current_timestamp - message_timestamp > TIME_LIMIT_SECONDS:
            print(f"INFO: Mensagem de {message_data.get('key', {}).get('remoteJid')} ignorada. Muito antiga.")
            continue  # Pula para a próxima mensagem

    # 1. Verificação do evento
    event_type = payload.get("event")
    if event_type != "MESSAGES_UPSERT":
        print(f"INFO: Evento ignorado: {event_type}")
        return {"status": "ignored_event", "event": event_type}

    print(f"Webhook recebido: {event_type} para instância {payload.get('instance')}")

    try:
        # 2. Iterar sobre as mensagens
        for message_data in payload.get("data", {}).get("messages", []):

            # Ignora mensagens enviadas pelo próprio bot
            if message_data.get("key", {}).get("fromMe"):
                continue

            # Extração da mensagem
            message_content = (
                    message_data.get("message", {}).get("conversation") or
                    message_data.get("message", {}).get("extendedTextMessage", {}).get("text")
            )
            conversation_id = message_data.get("key", {}).get("remoteJid")  # ID do cliente/conversa

            if not message_content or not conversation_id:
                continue

            # 3. Montar o objeto mensagem para o RAG
            message_obj = {
                "content": message_content,
                "sender": "cliente",
                "timestamp": int(time.time()),
                "message_id": message_data.get("key", {}).get("id") or str(time.time())
            }

            # 4. Adicionar a tarefa completa de processamento em background
            background_tasks.add_task(full_webhook_processing_task,
                                      conversation_id,
                                      message_obj,
                                      message_content)

    except Exception as e:
        print(f"❌ ERRO CRÍTICO no handle_evolution_webhook: {e}")
        # Retorna 200 para o Evolution não tentar re-enviar, mas loga o erro
        return {"status": "error_processing_payload", "detail": str(e)}

    return {"status": "received_and_processing"}


# Certifique-se de que as variáveis globais llm, db_tecnico, embeddings_model e playbook
# estão definidas no escopo de main.py (o que elas estão após cerebro_ia.load_models()).

# Em backend/main.py

# Certifique-se de que as variáveis globais llm, db_tecnico, embeddings_model e playbook
# estão definidas no escopo de main.py (o que elas estão após cerebro_ia.load_models()).
# Além disso, certifique-se de que o CONVERSATION_STATE_STORE foi adicionado.
def full_webhook_processing_task(conversation_id: str, message_obj: Dict[str, Any], query: str):
    """
    Função síncrona para ser executada em BackgroundTasks.
    Realiza a indexação, geração das sugestões e ATUALIZA O ESTADO GLOBAL.
    """
    global CONVERSATION_STATE_STORE

    # 1. Definir o estágio inicial (para novas conversas)
    initial_stage_id = playbook.get("initial_stage", "stage_triage")

    # 2. Indexar a mensagem no RAG da conversa
    try:
        conversation_db = cerebro_ia.get_or_create_conversation_db(conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(conversation_db, conversation_id, message_obj)
        print(f"✅ Mensagem do cliente indexada no RAG para JID: {conversation_id}")
    except Exception as e:
        print(f"❌ ERRO ao adicionar mensagem ao RAG: {e}")
        return  # Aborta a tarefa se a indexação falhar

    # 3. Gerar sugestões usando a função síncrona do core
    try:
        suggestions_response = cerebro_ia.generate_sales_suggestions(
            llm=llm,
            db_tecnico=db_tecnico,
            embeddings_model=embeddings_model,
            playbook=playbook,
            query=query,
            conversation_id=conversation_id,
            current_stage_id=initial_stage_id
        )

        # 4. ATUALIZAR O ESTADO GLOBAL com a nova mensagem e sugestões

        # Inicializa a estrutura da conversa se for nova
        if conversation_id not in CONVERSATION_STATE_STORE:
            # Você precisaria buscar o nome do cliente aqui (API Evolution ou DB)
            # Por simplicidade, vamos usar o JID como nome temporário
            CONVERSATION_STATE_STORE[conversation_id] = {
                "id": conversation_id,
                "name": f"Cliente: {conversation_id.split('@')[0]}",
                "stage_id": suggestions_response.get('new_stage_id', initial_stage_id),
                "messages": [],
                "suggestions": []
            }

        # Adiciona a mensagem do cliente ao histórico (para o frontend)
        CONVERSATION_STATE_STORE[conversation_id]["messages"].append(message_obj)

        # Atualiza as sugestões e o estágio
        CONVERSATION_STATE_STORE[conversation_id]["suggestions"] = suggestions_response.get('suggestions', {}).get(
            'follow_up_options', [])
        CONVERSATION_STATE_STORE[conversation_id]["stage_id"] = suggestions_response.get('new_stage_id',
                                                                                         initial_stage_id)

        print(f"✅ Estado da conversa {conversation_id} atualizado. Sugestões prontas.")

    except Exception as e:
        print(f"❌ ERRO ao gerar sugestões em background: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)