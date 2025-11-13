# Em backend/main.py

import os, time, httpx, uuid, json, uvicorn, asyncio, traceback
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any, List, Optional

# --- IMPORTAÇÕES (Corretas) ---
from core import security, cerebro_ia
from schemas import User, UserInDB, Token, NewConversationRequest
from services.conversation_service import ConversationService, get_conversation_service
from repositories.chroma_repository import get_conversations_repository # Mantenha este

# 💡 CORREÇÃO: Importa tudo do shared
from core.shared import (
    IA_MODELS, Colors,
    print_error, print_info, print_success, print_warning
)
# --- Importando os Routers ---
from routers import evolution as evolution_router
from routers import conversations as conversations_router

# 💡 CORREÇÃO: Definições de Colors e print_... REMOVIDAS daqui.
# Elas agora vivem exclusivamente em core/shared.py

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections: del self.active_connections[client_id]

    async def broadcast(self, message: str):
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_text(message)
            except WebSocketDisconnect:
                self.disconnect(client_id)
            except Exception as e:
                print_error(f"Erro ao transmitir para {client_id}: {e}")
                self.disconnect(client_id)

manager = ConnectionManager()
# --- Fim das Classes Auxiliares ---

# --- Variáveis de Ambiente ---
load_dotenv()
EVOLUTION_API_URL = "http://34.29.184.203:8080"
print("---------------------------------------------------")
print(f"🔍 DEBUG: O Backend está tentando conectar em: {EVOLUTION_API_URL}")
print("---------------------------------------------------")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "cosmos-test")
MODE = os.getenv("MODE", "chat")

# O dicionário IA_MODELS está em core/shared.py

# --- Inicialização do App ---
app = FastAPI(title="Backend Venai Refatorado")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(evolution_router.router)
app.include_router(conversations_router.router)


# --- FUNÇÃO DE PARSING (Correta) ---
def _parse_message_content(msg_content_obj: Dict[str, Any]) -> Optional[str]:
    """ Extrai o conteúdo de texto de vários tipos de mensagem da Evolution API. """
    if not msg_content_obj:
        return None
    if "conversation" in msg_content_obj:
        return msg_content_obj["conversation"]
    if "extendedTextMessage" in msg_content_obj:
        return msg_content_obj.get("extendedTextMessage", {}).get("text")
    if "templateMessage" in msg_content_obj:
        hydrated_template = msg_content_obj.get("templateMessage", {}).get("hydratedFourRowTemplate", {})
        if hydrated_template and "hydratedContentText" in hydrated_template:
            return hydrated_template["hydratedContentText"]
        return None
    if "imageMessage" in msg_content_obj:
        return msg_content_obj.get("imageMessage", {}).get("caption")
    if "videoMessage" in msg_content_obj:
        return msg_content_obj.get("videoMessage", {}).get("caption")
    return None


# --- FUNÇÃO DE SINCRONIZAÇÃO (Correta) ---
async def sincronizar_historico_inicial(service: ConversationService):
    """
    Busca o histórico de mensagens da Evolution API (com paginação)
    e popula o ChromaDB (Repositório) para o "cold start".
    """
    print_info("🔄 [Sync] Iniciando sincronização de histórico da Evolution API...")

    # --- Etapa 1: Buscar mapa de nomes (JID -> Nome) ---
    headers = {"apikey": EVOLUTION_API_KEY, "Accept": "application/json"}
    mapa_de_nomes = {}

    try:
        print_info("ℹ️  [Sync] Etapa 1: Buscando mapa de nomes (findChats)...")
        chats_url = f"{EVOLUTION_API_URL}/chat/findChats/{INSTANCE_NAME}"  #
        headers = {"apikey": EVOLUTION_API_KEY, "Accept": "application/json"}  #
        async with httpx.AsyncClient(timeout=120.0) as client:
            print_info(f"ℹ️  [Sync DEBUG] Fazendo POST para: {chats_url}")
            # 💡 CORREÇÃO: O endpoint findChats espera um POST, mesmo sem corpo.
            response = await client.post(chats_url, headers=headers)
            response.raise_for_status()
            chats_response_data = response.json()

            for chat in chats_response_data:
                jid = chat.get("jid")
                name = chat.get("name") or chat.get("notSpam")
                if jid and name:
                    mapa_de_nomes[jid] = name

        print_success(f"✅ [Sync] Etapa 1: Mapa de {len(mapa_de_nomes)} nomes criado.")
    except httpx.HTTPStatusError as e:
        print_error(f"❌ [Sync] Erro de Status da API Evolution (findChats): {e.response.status_code} - {e.response.text}")
        return # Interrompe a sincronização se a primeira etapa falhar
    except Exception as e:
        print_error(f"❌ [Sync] Erro inesperado na Etapa 1 (findChats): {repr(e)}")
        traceback.print_exc()
        return # Interrompe a sincronização

    # --- Etapa 2: Buscar histórico de mensagens ---
    try:
        print_info("ℹ️  [Sync] Etapa 2: Buscando histórico de mensagens (findMessages)...")
        messages_url = f"{EVOLUTION_API_URL}/chat/findMessages/{INSTANCE_NAME}"
        PAGINAS_PARA_BUSCAR = 200  # 💡 Variável movida para o escopo correto
        mensagens_encontradas_total = 0
        mensagens_salvas_total = 0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for page in range(1, PAGINAS_PARA_BUSCAR + 1):
                payload = {"page": page, "pageSize": 250}
                print_info(f"ℹ️  [Sync] Buscando página {page}/{PAGINAS_PARA_BUSCAR}...")
                # 💡 CORREÇÃO: O endpoint findMessages também é POST e usa o payload
                response = await client.post(messages_url, headers=headers, json=payload)
                response.raise_for_status()

                data = response.json()
                messages = data.get("messages", {}).get("records", [])

                if not messages:
                    print_warning(f"⚠️ [Sync] Nenhuma mensagem encontrada na página {page}. Interrompendo.")
                    break

                mensagens_encontradas_total += len(messages)

                for msg_data in messages:
                    key = msg_data.get("key", {})
                    sender_jid = key.get("remoteJid")

                    if not sender_jid or not sender_jid.endswith("@s.whatsapp.net"):
                        continue

                    msg_content_obj = msg_data.get("message", {})
                    message_content = _parse_message_content(msg_content_obj)
                    if not message_content:
                        continue

                    push_name_api = msg_data.get("pushName")
                    nome_do_mapa = mapa_de_nomes.get(sender_jid)

                    message_obj = {
                        "message_id": key.get("id"),
                        "contact_id": sender_jid,
                        "content": message_content,
                        "sender": "vendedor" if key.get("fromMe", False) else "cliente",
                        "timestamp": int(msg_data.get("messageTimestamp", time.time())),
                        "pushName": nome_do_mapa or push_name_api or sender_jid.split('@')[0],
                        "instance_id": msg_data.get("instanceId", INSTANCE_NAME)
                    }

                    await service.save_message_from_webhook(message_obj)
                    mensagens_salvas_total += 1

        print_success(
            f"✅ [Sync] Sincronização concluída. {mensagens_encontradas_total} mensagens lidas, {mensagens_salvas_total} mensagens 1-para-1 salvas no ChromaDB.")

    except httpx.HTTPStatusError as e:
        print_error(
            f"❌ [Sync] Erro de Status da API Evolution (findMessages): {e.response.status_code} - {e.response.text}")
    except Exception as e:
        print_error(f"❌ [Sync] Erro inesperado durante a sincronização: {repr(e)}")
        traceback.print_exc()


# --- FIM DAS ATUALIZAÇÕES DE SYNC ---


@app.on_event("startup")
async def startup_event():
    """
    Inicializa o servidor, o repositório de conversas e,
    crucialmente, carrega os modelos de IA (o "cérebro").
    """
    print_info("INFO: Iniciando servidor e serviços...")
    global IA_MODELS  # Permite modificar o dicionário global de core.shared

    # 1. Inicializa o serviço de conversas (como antes)
    try:
        repo = get_conversations_repository()

        service_instance = ConversationService(repository=repo)
        print_info("✅ Conexão inicial com o Repositório verificada.")

        # print_warning("⚠️  [Startup] Limpando dados da coleção anterior (LGPD)...")
        # await service_instance.delete_all_conversations()

        print_info("ℹ️  Agendando Sincronização de Histórico (Cold Start)...")
        asyncio.create_task(sincronizar_historico_inicial(service_instance))

    except Exception as e:
        print_error(f"❌ Falha ao inicializar o Chroma Repository no startup: {e}")
        traceback.print_exc()

    # 2. Verifica o MODO e inicializa a IA
    if MODE == "chat":
        print_warning("=====================================================")
        print_warning("⚠️ MODO CHAT ATIVADO: Inicialização da IA desabilitada.")
        print_warning("   Para ativar, defina a variável de ambiente MODE=copilot (ou similar).")
        print_warning("=====================================================")
    else:
        print_info(f"ℹ️  MODO '{MODE}' detectado. Inicializando o Cérebro (IA)...")
        # try:
        #     # ETAPA 2.1: Conectar ao ChromaDB (Cérebro 1)
        #     # Usando a função de `cerebro_ia.py`
        #     client = cerebro_ia.initialize_chroma_client()
        #     if not client:
        #         raise ConnectionError("Não foi possível conectar ao ChromaDB.")
        #
        #     IA_MODELS["chroma_client"] = client
        #
        #     # ETAPA 2.2: Carregar todos os modelos
        #     # Usando a função de `cerebro_ia.py`
        #     llm, retriever, embeddings, playbook = cerebro_ia.load_models(client)
        #
        #     # Armazena os modelos carregados nas variáveis globais
        #     IA_MODELS["llm"] = llm
        #     IA_MODELS["retriever"] = retriever
        #     IA_MODELS["embeddings"] = embeddings
        #     IA_MODELS["playbook"] = playbook
        #
        #     print_success("✅ Cérebro (IA) inicializado e modelos carregados com sucesso.")
        #
        # except Exception as e:
        #     print_error(f"❌ FALHA CRÍTICA ao inicializar a IA: {e}")
        #     traceback.print_exc()  # Imprime o stack trace completo

    print_info("✅ Servidor pronto. Aguardando webhooks...")


# --- Endpoints de Autenticação ---
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = security.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha incorretos",
                            headers={"WWW-Authenticate": "Bearer"})
    access_token = security.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(security.get_current_active_user)):
    return current_user


# --- Lógica de Processamento ---
async def process_and_save_message(
        message_obj: Dict[str, Any],
        service: ConversationService
):
    try:
        await service.save_message_from_webhook(message_obj)
    except Exception as e:
        print_error(f"❌ [ProcessMsg] Falha ao salvar mensagem via serviço: {e}")


async def send_whatsapp_message(recipient_jid: str, message_text: str) -> bool:
    api_url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    payload = {
        "number": recipient_jid.split('@')[0],
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": message_text}
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload, timeout=30.0)
            if response.status_code in [200, 201]:
                print_success(f"Mensagem enviada para {recipient_jid}: {message_text}")
                return True
            else:
                print_error(f"Falha ao enviar mensagem para {recipient_jid} ({response.status_code}): {response.text}")
                return False
    except Exception as e:
        print_error(f"Exceção ao enviar mensagem para {recipient_jid}: {e}")
        return False

def _create_service_instance() -> ConversationService:
    # 💡 CORREÇÃO: Usa a factory para criar a instância
    repo = get_conversations_repository()
    service = ConversationService(repository=repo)
    return service


@app.post("/webhook/evolution")
async def webhook_evolution(
        request: Request,
        background_tasks: BackgroundTasks,
        service: ConversationService = Depends(get_conversation_service)
):
    try:
        data = await request.json()
        print_info(f"===== NOVO WEBHOOK RECEBIDO =====")
        print_info(json.dumps(data, indent=2))

        event = data.get("event")

        if event == "messages.upsert" and data.get("data", {}).get("messageType"):
            message_data = data.get("data", {})
            key = message_data.get("key", {})
            sender_jid = key.get("remoteJid")

            if not sender_jid or not sender_jid.endswith("@s.whatsapp.net"):
                return {"status": "ok", "message": "Ignorado (grupo ou sem JID)"}

            msg_content_obj = message_data.get("message", {})
            message_content = _parse_message_content(msg_content_obj)

            if not message_content:
                print_info(f"ℹ️  [Webhook] Ignorando mensagem sem texto (Tipo: {message_data.get('messageType')}).")
                return {"status": "ok", "message": "Ignorado (sem texto)"}

            message_obj = {
                "message_id": key.get("id"),
                "contact_id": sender_jid,
                "content": message_content,
                "sender": "vendedor" if key.get("fromMe", False) else "cliente",
                "timestamp": int(message_data.get("messageTimestamp", time.time())),
                "pushName": message_data.get("pushName", sender_jid.split('@')[0]),
                "instance_id": data.get("instance", INSTANCE_NAME)
            }

            # 💡 CORREÇÃO: Chama o método do serviço diretamente
            background_tasks.add_task(service.save_message_from_webhook, message_obj)

        # 💡 CORREÇÃO (LGPD): Agora funciona pois 'event' está definido
        elif event == "instance.logout" or (
                event == "connection.update" and data.get("data", {}).get("state") == "close"):
            print_warning("⚠️ [LGPD] Evento de LOGOUT/DESCONEXÃO detectado. Agendando limpeza do banco de dados...")
            background_tasks.add_task(service.delete_all_conversations)

        else:
            print_info(f"ℹ️  [Webhook] Evento '{event}' recebido e ignorado (não é 'messages.upsert' nem 'logout').")

        return {"status": "ok", "received": True}
    except Exception as e:
        print_error(f"Erro ao processar webhook: {e}")
        traceback.print_exc()  # Adiciona mais detalhes do erro
        return {"status": "error", "message": str(e)}


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)
        print_info(f"Cliente {client_id} desconectado.")


# --- Endpoint de Nova Conversa (Correto) ---
@app.post("/new-conversation")
async def start_new_conversation(
        request_data: NewConversationRequest,  # Nome da variável mudado
        background_tasks: BackgroundTasks,
        current_user: User = Depends(security.get_current_active_user),
        # 💡 CORREÇÃO: Pega o serviço por Injeção de Dependência
        service: ConversationService = Depends(get_conversation_service)
):
    """
    Este endpoint agora apenas CRIA a mensagem no DB.
    O envio real é feito pelo frontend chamando /evolution/message/send
    """
    recipient_jid = f"{request_data.recipient_number}@s.whatsapp.net"

    # 💡 NOTA: A lógica de envio FOI MOVIDA para /evolution/message/send
    # Este endpoint agora apenas salva a mensagem inicial do vendedor

    message_obj = {
        "message_id": f"seller_init_{uuid.uuid4()}",  # Cria um ID único
        "contact_id": recipient_jid,
        "content": request_data.initial_message,
        "sender": "vendedor",
        "timestamp": int(time.time()),
        "pushName": current_user.full_name or "Vendedor",
        "instance_id": INSTANCE_NAME
    }

    # 💡 CORREÇÃO: Chama o método do serviço diretamente
    background_tasks.add_task(
        service.save_message_from_webhook,
        message_obj
    )
    return {"status": "success", "message": "Conversa iniciada e salva localmente."}


# --- Ponto de Entrada ---
if __name__ == "__main__":
    print_info("🚀 Iniciando servidor backend (Refatorado)...")
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080)), reload=True)