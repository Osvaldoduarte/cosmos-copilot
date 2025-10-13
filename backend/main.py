import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
# NOVO: Importa o CORSMiddleware
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any

from core import cerebro_ia

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


print("INFO: Carregando modelos e playbook na inicialização do servidor...")
llm, db_tecnico, embeddings_model, playbook = cerebro_ia.load_models()
print("✅ Modelos e playbook carregados. Servidor pronto.")


# --- 2. Definição dos Modelos de Dados (Pydantic) ---
# ... (sem alterações aqui)
class SuggestionRequest(BaseModel):
    query: str
    conversation_id: str
    current_stage_id: str | None = Field(default=None)

# ... (seu modelo EvolutionPayload permanece o mesmo)


# --- 3. Endpoints da API ---
# ... (seus endpoints @app.post permanecem os mesmos)


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

@app.post("/webhook/evolution")
async def handle_evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    print(f"Webhook recebido da Evolution API.")
    try:
        message_data = payload.get("data", {})
        message_content = message_data.get("message", {}).get("conversation")
        conversation_id = message_data.get("key", {}).get("remoteJid")
        if not message_content or not conversation_id:
            return {"status": "ignored_no_content"}
        message_obj = { "content": message_content, "sender": "cliente" if not message_data.get("key", {}).get("fromMe") else "vendedor", "timestamp": payload.get("timestamp"), "message_id": message_data.get("key", {}).get("id") }
    except Exception as e:
        print(f"❌ ERRO ao processar o payload do webhook: {e}")
        return {"status": "error_processing_payload"}
    def index_message_task():
        conversation_db = cerebro_ia.get_or_create_conversation_db(conversation_id, embeddings_model)
        cerebro_ia.add_message_to_conversation_rag(conversation_db, conversation_id, message_obj)
    background_tasks.add_task(index_message_task)
    return {"status": "received_and_processing"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)