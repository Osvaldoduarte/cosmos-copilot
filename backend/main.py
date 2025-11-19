import os
import time
import httpx
import uuid
import json
import uvicorn
import asyncio
import base64
import traceback
import io
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect, Depends, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any, List, Optional

# --- IMPORTAÇÕES DO NÚCLEO ---
from core import security
import core.cerebro_ia as cerebro_ia

from schemas import User, UserInDB, Token, NewConversationRequest, CopilotAnalyzeRequest
from services.conversation_service import ConversationService, get_conversation_service
from repositories.chroma_repository import get_conversations_repository

from routers import websocket as websocket_router # ✨ NOVO: Adicione o import do router
from services.websocket_manager import manager

from core.shared import (
    IA_MODELS, Colors,
    print_error, print_info, print_success, print_warning
)

from routers import evolution as evolution_router
from routers import conversations as conversations_router


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
            except Exception:
                self.disconnect(client_id)


manager = ConnectionManager()

load_dotenv()
EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://34.29.184.203:8080")
if EVOLUTION_API_URL.endswith('/'): EVOLUTION_API_URL = EVOLUTION_API_URL[:-1]
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "cosmos-test")
MODE = os.getenv("MODE", "copilot")

app = FastAPI(title="Backend Venai - Venda Inteligente")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui os routers (Mantenha o evolution_router para outras coisas, mas o proxy de mídia está aqui embaixo)
app.include_router(evolution_router.router)
app.include_router(conversations_router.router)
app.include_router(websocket_router.router)


# ==========================================
#  LÓGICA CENTRAL DE PROXY DE MÍDIA (CORAÇÃO)
# ==========================================
@app.get("/evolution/media-proxy")
async def public_media_proxy(url: str, messageId: str = None):
    # 1. Tenta URL Original
    try:
        decoded_url = base64.b64decode(url).decode('utf-8')
        target_url = decoded_url if decoded_url.startswith("http") else url
    except:
        target_url = url

    try:
        async with httpx.AsyncClient(verify=False) as client:
            try:
                r = await client.get(target_url, timeout=5.0)
                if r.status_code != 200: raise Exception("Fail")
            except:
                r = await client.get(target_url, headers={"apikey": EVOLUTION_API_KEY}, timeout=5.0)

            if r.status_code == 200:
                content_type = r.headers.get("content-type", "")

                # 💡 O PULO DO GATO:
                # Se a URL original devolver "octet-stream" (genérico), nós FORÇAMOS O ERRO
                # para cair no "Plano B" (Resgate) que sabe o tipo certo do arquivo.
                if "octet-stream" in content_type or not content_type:
                    raise Exception("MIME Type inválido, tentando resgate...")

                return StreamingResponse(
                    r.aiter_bytes(),
                    media_type=content_type,
                    headers={
                        "Cache-Control": "public, max-age=31536000",
                        "Access-Control-Allow-Origin": "*",
                        "Content-Disposition": "inline"
                    }
                )
    except:
        pass  # Falhou ou era genérico, vai para o resgate

    # 2. Resgate via Evolution (PLANO B - SALVA VIDAS)
    if messageId:
        try:
            rescue_url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{INSTANCE_NAME}"
            payload = {"message": {"key": {"id": messageId}}, "convertToMp4": False}

            async with httpx.AsyncClient() as client:
                res = await client.post(
                    rescue_url,
                    headers={"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"},
                    json=payload,
                    timeout=30.0
                )

                # Aceita 200 ou 201 (Created)
                if res.status_code in [200, 201]:
                    data = res.json()
                    base64_str = data.get("base64")

                    # A Evolution manda o mimetype correto aqui!
                    mimetype = data.get("mimetype")

                    # Se ainda assim falhar, adivinhamos na força bruta
                    if not mimetype or "application" in mimetype:
                        media_type_hint = data.get("mediaType") or ""
                        if "audio" in media_type_hint:
                            mimetype = "audio/mpeg"
                        elif "image" in media_type_hint:
                            mimetype = "image/jpeg"
                        elif "video" in media_type_hint:
                            mimetype = "video/mp4"
                        else:
                            mimetype = "image/jpeg"

                    if base64_str:
                        import io
                        file_bytes = base64.b64decode(base64_str)
                        print(f"✅ [Proxy] Resgate Sucesso! MIME: {mimetype}")

                        return StreamingResponse(
                            io.BytesIO(file_bytes),
                            media_type=mimetype,
                            headers={
                                "Cache-Control": "public, max-age=31536000",
                                "Access-Control-Allow-Origin": "*",
                                "Content-Type": mimetype,
                                "Content-Disposition": "inline"
                            }
                        )
        except Exception as e:
            print(f"❌ [Proxy] Erro Resgate: {e}")

    # Retorna pixel transparente (para não ficar aquele ícone quebrado feio)
    empty_pixel = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    return StreamingResponse(io.BytesIO(empty_pixel), media_type="image/gif")

# --- ROTAS PÚBLICAS (SEM AUTH) ---
# Mapeia tanto a rota nova quanto a antiga (cache) para o mesmo handler
@app.get("/public/media")
async def route_public_media(url: str, messageId: str = None):
    return await public_media_proxy(url, messageId)


@app.get("/evolution/media-proxy")
async def route_legacy_media(url: str, messageId: str = None):
    return await public_media_proxy(url, messageId)


# ==========================================
#  OUTRAS FUNÇÕES E ROTAS DO SISTEMA
# ==========================================

def _extract_message_data(msg_obj: Dict[str, Any]) -> Dict[str, Any]:
    result = {"content": "", "media_type": "text", "media_url": None}
    if not msg_obj: return result

    if "conversation" in msg_obj:
        result["content"] = msg_obj["conversation"]
    elif "extendedTextMessage" in msg_obj:
        result["content"] = msg_obj["extendedTextMessage"].get("text", "")

    media_types = {
        "imageMessage": "image", "videoMessage": "video",
        "audioMessage": "audio", "documentMessage": "document", "stickerMessage": "image"
    }
    for key, type_name in media_types.items():
        if key in msg_obj:
            media = msg_obj[key]
            result["media_type"] = type_name
            result["content"] = media.get("caption") or media.get("fileName") or ""
            if key == "audioMessage" and media.get("ptt"): result["content"] = "[Mensagem de Voz]"

            b64 = media.get("base64")
            url = media.get("url")

            if b64:
                mime = media.get("mimetype", "image/jpeg")
                result["media_url"] = f"data:{mime};base64,{b64}"
            elif url:
                result["media_url"] = url
            break
    return result


async def executar_sincronizacao(service: ConversationService, paginas: int = 200):
    LIMITE_CHATS = 150
    LIMITE_MSGS_POR_CHAT = 200
    print_info(f"🔄 [Sync] Iniciando Sincronização Profunda...")
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}

    # 1. Mapeia Nomes e Fotos
    mapa_nomes = {}
    mapa_fotos = {}
    try:
        url_chats = f"{EVOLUTION_API_URL}/chat/findChats/{INSTANCE_NAME}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url_chats, headers=headers)
            if r.status_code != 200: r = await client.post(url_chats, headers=headers)
            if r.status_code == 200:
                lista = r.json()
                if isinstance(lista, dict): lista = lista.get('chats', [])
                for c in lista:
                    if c.get("id"):
                        mapa_nomes[c.get("id")] = c.get("name") or c.get("pushName")
                        mapa_fotos[c.get("id")] = c.get("profilePictureUrl") or c.get("image")
    except:
        pass

    cache_fotos = {}
    url_msgs = f"{EVOLUTION_API_URL}/chat/findMessages/{INSTANCE_NAME}"
    chats_processados = {}

    async with httpx.AsyncClient(timeout=60.0) as client:
        for page in range(1, paginas + 1):
            if len(chats_processados) >= LIMITE_CHATS:
                if all(c >= LIMITE_MSGS_POR_CHAT for c in chats_processados.values()): break
            try:
                print_info(f"📄 [Sync] Página {page}...")
                resp = await client.post(url_msgs, headers=headers, json={"page": page, "pageSize": 200})
                msgs = resp.json().get("messages", {}).get("records", [])
                if not msgs: break

                for m in msgs:
                    key = m.get("key", {})
                    remote_jid = key.get("remoteJid")
                    if not remote_jid or "@g.us" in remote_jid: continue
                    if not remote_jid.endswith("@s.whatsapp.net"): continue

                    if remote_jid not in chats_processados:
                        if len(chats_processados) >= LIMITE_CHATS: continue
                        chats_processados[remote_jid] = 0
                    if chats_processados[remote_jid] >= LIMITE_MSGS_POR_CHAT: continue

                    # Busca foto se não tiver
                    if remote_jid not in cache_fotos:
                        if remote_jid in mapa_fotos and mapa_fotos[remote_jid]:
                            cache_fotos[remote_jid] = mapa_fotos[remote_jid]
                        else:
                            try:
                                num = remote_jid.split('@')[0]
                                url_foto = f"{EVOLUTION_API_URL}/chat/fetchProfilePictureUrl/{INSTANCE_NAME}"
                                res_foto = await client.post(url_foto, headers=headers, json={"number": num})
                                if res_foto.status_code == 200:
                                    data_foto = res_foto.json()
                                    cache_fotos[remote_jid] = data_foto.get("profilePictureUrl") or data_foto.get(
                                        "picture")
                                else:
                                    cache_fotos[remote_jid] = None
                            except:
                                cache_fotos[remote_jid] = None

                    extracted = _extract_message_data(m.get("message", {}))
                    if not extracted["content"] and not extracted["media_url"]: continue

                    ts = int(m.get("messageTimestamp", time.time()))
                    is_me = key.get("fromMe", False)
                    nome = mapa_nomes.get(remote_jid) or m.get("pushName") or remote_jid.split('@')[0]

                    msg_obj = {
                        "message_id": key.get("id"),
                        "contact_id": remote_jid,
                        "content": extracted["content"],
                        "media_type": extracted["media_type"],
                        "media_url": extracted["media_url"],
                        "sender": "vendedor" if is_me else "cliente",
                        "timestamp": ts,
                        "pushName": nome,
                        "instance_id": INSTANCE_NAME,
                        "profilePicUrl": cache_fotos.get(remote_jid)
                    }
                    await service.save_message_from_webhook(msg_obj)
                    chats_processados[remote_jid] += 1
            except:
                pass
    print_success(f"✅ [Sync] Concluído!")


sincronizar_historico_inicial = executar_sincronizacao


@app.on_event("startup")
async def startup_event():
    print_info("🚀 Iniciando Backend...")
    global IA_MODELS
    try:
        repo = get_conversations_repository()
        service = ConversationService(repository=repo)
        asyncio.create_task(sincronizar_historico_inicial(service, paginas=50))
    except:
        pass

    if MODE != "chat":
        print_info(f"ℹ️  Inicializando IA...")
        try:
            client = cerebro_ia.initialize_chroma_client()
            if client:
                models = cerebro_ia.load_models(client)
                IA_MODELS.update(zip(["llm", "retriever", "embeddings", "playbook"], models))
                IA_MODELS["chroma_client"] = client
                print_success("✅ Cérebro IA Carregado!")
        except:
            traceback.print_exc()


@app.post("/copilot/analyze")
async def analyze_conversation(req: CopilotAnalyzeRequest, user: User = Depends(security.get_current_active_user),
                               service: ConversationService = Depends(get_conversation_service)):
    if not IA_MODELS.get("llm"): raise HTTPException(status_code=503, detail="IA offline.")
    sales_copilot = cerebro_ia.get_sales_copilot()
    messages = await service.get_messages_for_conversation(req.contact_id)
    history_simple = []
    for m in messages:
        content = m.get("content", "")
        if m.get("media_type") == "audio":
            content = "[ÁUDIO]"
        elif m.get("media_type") == "image":
            content = f"[IMAGEM]: {content}"
        history_simple.append({"sender": m.get("sender"), "content": content})
    try:
        return sales_copilot.generate_sales_suggestions(query=req.query, full_conversation_history=history_simple,
                                                        current_stage_id="general", is_private_query=req.is_private,
                                                        client_data={})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/evolution")
async def webhook(request: Request, background_tasks: BackgroundTasks,
                  service: ConversationService = Depends(get_conversation_service)):
    try:
        data = await request.json()
        if data.get("event") == "messages.upsert":
            msg_data = data.get("data", {})
            jid = msg_data.get("key", {}).get("remoteJid")
            if jid and "@g.us" not in jid:
                extracted = _extract_message_data(msg_data.get("message", {}))
                obj = {
                    "message_id": msg_data.get("key", {}).get("id"),
                    "contact_id": jid,
                    "content": extracted["content"],
                    "media_type": extracted["media_type"],
                    "media_url": extracted["media_url"],
                    "sender": "vendedor" if msg_data.get("key", {}).get("fromMe") else "cliente",
                    "timestamp": int(msg_data.get("messageTimestamp", time.time())),
                    "pushName": msg_data.get("pushName", jid.split('@')[0]),
                    "instance_id": data.get("instance", INSTANCE_NAME),
                    "profilePicUrl": msg_data.get("senderPhoto")
                }
                # 1. Encontrar o usuário que possui esta instância
                # (ATENÇÃO: Este é um ponto chave de lógica de negócio que deve ser implementado no seu sistema)
                # Por hora, vamos assumir que o 'vendedor1' é o único que usa o app.

                # ✨ Lógica Simples (Troque por sua busca real no DB)
                # Você precisa de uma forma de mapear INSTANCE_NAME para um USERNAME (user_id)
                # Exemplo: user_id = await get_user_from_instance_db(obj["instance_id"])
                user_id_to_notify = "vendedor1"  # <--- SUBSTITUA PELA LÓGICA DE BUSCA REAL!

                # 2. Transforma o objeto em um formato ideal para o frontend
                # O frontend precisa de tudo para atualizar a lista de conversas
                # O objeto 'obj' é o formato final.

                # 3. Envia para o WebSocket
                background_tasks.add_task(manager.broadcast, user_id_to_notify, obj)

                background_tasks.add_task(service.save_message_from_webhook, obj)
        return {"status": "received"}
    except:
        return {"status": "error"}


@app.post("/new-conversation")
async def start_new_conversation(req: NewConversationRequest, background_tasks: BackgroundTasks,
                                 user: User = Depends(security.get_current_active_user),
                                 service: ConversationService = Depends(get_conversation_service)):
    jid = f"{req.recipient_number}@s.whatsapp.net"
    raw = req.recipient_number
    if raw.startswith("55") and len(raw) == 13:
        short = raw[:4] + raw[5:]
        short_jid = f"{short}@s.whatsapp.net"
        if await service.get_messages_for_conversation(short_jid): jid = short_jid; raw = short

    try:
        async with httpx.AsyncClient() as client:
            await client.post(f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}",
                              headers={"apikey": EVOLUTION_API_KEY}, json={"number": raw, "text": req.initial_message})
    except:
        pass

    msg = {"message_id": f"init_{uuid.uuid4()}", "contact_id": jid, "content": req.initial_message,
           "sender": "vendedor", "timestamp": int(time.time()), "pushName": user.full_name,
           "instance_id": INSTANCE_NAME, "media_type": "text", "media_url": None}
    background_tasks.add_task(service.save_message_from_webhook, msg)
    return {"status": "success", "contact_id": jid}


@app.post("/system/sync-history")
async def manual_sync(pages: int = 5, service: ConversationService = Depends(get_conversation_service)):
    asyncio.create_task(executar_sincronizacao(service, paginas=pages))
    return {"status": "processing"}


@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = security.authenticate_user(form_data.username, form_data.password)
    if not user: raise HTTPException(status_code=401, detail="Credenciais inválidas")
    return {"access_token": security.create_access_token(data={"sub": user.username}), "token_type": "bearer"}


@app.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    Endpoint WebSocket que autentica usando um token na URL.
    """
    try:
        # ✨ PASSO IMPORTANTE:
        # Você precisa de uma função que decodifique o JWT
        # e retorne o ID do usuário.
        user_id = get_user_id_from_token(token)

        if user_id is None:
            await websocket.close(code=1008)  # Código de política violada
            return

        # Conecta o usuário ao gerenciador
        await manager.connect(user_id, websocket)

        # Mantém a conexão viva
        while True:
            # Apenas espera por mensagens (ou desconexão)
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        print(f"Erro no WebSocket: {e}")
        if 'user_id' in locals():
            manager.disconnect(user_id, websocket)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)