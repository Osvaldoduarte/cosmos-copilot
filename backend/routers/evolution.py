# Em backend/routers/evolution.py
import httpx
import os
import traceback
import uuid
import time
import base64
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.security import get_current_active_user, get_current_user
from schemas import UserInDB, User, FetchProfilePictureRequest
from services.conversation_service import ConversationService, get_conversation_service
from core.shared import print_error, print_info, print_warning, print_success

router = APIRouter(
    prefix="/evolution",
    tags=["Evolution API Proxy"],
    dependencies=[Depends(get_current_active_user)]
)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://34.29.184.203:8080")
if EVOLUTION_API_URL.endswith('/'): EVOLUTION_API_URL = EVOLUTION_API_URL[:-1]

EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "cosmos-test")


class SendMessageRequest(BaseModel):
    recipient_jid: str = Field(..., alias="contact_id")
    message_text: str = Field(..., alias="text")

    class Config:
        populate_by_name = True
        extra = "ignore"


# ... (Rotas QR, Status, Send Message e Profile Picture mantidas IGUAIS) ...
# ... (Copie as rotas create_and_get_qr, instance_status, send_message e fetchProfilePictureUrl do código anterior se precisar, ou mantenha o arquivo e substitua só a media_proxy abaixo) ...

@router.post("/instance/create_and_get_qr")
async def proxy_get_qr_code(request: Request, current_user: UserInDB = Depends(get_current_user)):
    try:
        try:
            frontend_body = await request.json()
        except:
            frontend_body = {}

        instance_name = frontend_body.get("instanceName") or INSTANCE_NAME
        headers = {"apikey": EVOLUTION_API_KEY}

        print_info(f"🔌 Tentando conectar na instância: {instance_name}")

        async with httpx.AsyncClient() as client:
            # 1. Tenta conectar (pegar QR Code existente)
            connect_url = f"{EVOLUTION_API_URL}/instance/connect/{instance_name}"
            response = await client.get(connect_url, headers=headers, timeout=20.0)

            # Se deu 401, a chave está errada. Para tudo.
            if response.status_code == 401:
                print_error("❌ Erro 401: API Key da Evolution incorreta.")
                raise HTTPException(status_code=502, detail="Erro de Autenticação no Backend (API Key inválida)")

            # Se deu sucesso (200), retorna o QR Code
            if response.status_code == 200:
                return response.json()

            # 2. Se deu 404 (Não encontrada), vamos CRIAR a instância
            if response.status_code == 404:
                print_warning(f"⚠️ Instância '{instance_name}' não existe. Criando nova...")

                create_url = f"{EVOLUTION_API_URL}/instance/create"
                payload = {
                    "instanceName": instance_name,
                    "token": "",  # Opcional, pode deixar vazio ou gerar um token
                    "qrcode": True,
                    "integration": "WHATSAPP-BAILEYS"
                }

                create_response = await client.post(create_url, headers=headers, json=payload, timeout=30.0)

                if create_response.status_code == 201:  # Criado com sucesso
                    print_success(f"✅ Instância '{instance_name}' criada com sucesso!")
                    return create_response.json()
                else:
                    # Se falhar ao criar
                    print_error(f"❌ Falha ao criar instância: {create_response.text}")
                    raise HTTPException(status_code=create_response.status_code, detail=create_response.text)

            # Se for outro erro qualquer
            raise HTTPException(status_code=response.status_code, detail=response.text)

    except HTTPException as he:
        raise he
    except Exception as e:
        print_error(f"❌ Erro Crítico Proxy QR: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instance/status")
async def proxy_instance_status(request: Request, current_user: UserInDB = Depends(get_current_user)):
    instance_name = request.query_params.get('instanceName') or INSTANCE_NAME
    api_url = f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}"
    headers = {"apikey": EVOLUTION_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(api_url, headers=headers)
            return response.json()
    except Exception as e:
        return {"instance": {"state": "close"}}


@router.post("/message/send")
async def proxy_send_message(
        request_data: SendMessageRequest,
        background_tasks: BackgroundTasks,
        current_user: User = Depends(get_current_active_user),
        service: ConversationService = Depends(get_conversation_service)
):
    api_url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}

    jid = request_data.recipient_jid
    if "@" not in jid:
        jid = f"{jid}@s.whatsapp.net"

    payload = {
        "number": jid.split('@')[0],
        "text": request_data.message_text,
        "delay": 1200,
        "linkPreview": False
    }

    print_info(f"📤 [Proxy] Enviando msg para {jid}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()
            response_data = response.json()
            msg_id = response_data.get("key", {}).get("id", f"sent_{uuid.uuid4()}")

        message_obj = {
            "message_id": msg_id,
            "contact_id": jid,
            "content": request_data.message_text,
            "sender": "vendedor",
            "timestamp": int(time.time()),
            "pushName": current_user.full_name or "Vendedor",
            "instance_id": INSTANCE_NAME
        }
        background_tasks.add_task(service.save_message_from_webhook, message_obj)
        return response_data

    except httpx.HTTPStatusError as e:
        print_error(f"❌ Erro API Evolution: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        print_error(f"❌ Erro Interno Envio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/fetchProfilePictureUrl/{instance_name}")
async def proxy_fetch_profile_picture(
        instance_name: str,
        request_data: FetchProfilePictureRequest,
        current_user: User = Depends(get_current_active_user)
):
    real_api_url = f"{EVOLUTION_API_URL}/chat/fetchProfilePictureUrl/{instance_name}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}
    number = request_data.number.replace("@s.whatsapp.net", "")
    payload = {"number": number}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(real_api_url, headers=headers, json=payload, timeout=10.0)
            if response.status_code == 404:
                return {"profilePictureUrl": None}
            response.raise_for_status()
            data = response.json()
            url = data.get("profilePictureUrl") or data.get("picture")
            return {"profilePictureUrl": url}
    except Exception as e:
        return {"profilePictureUrl": None}


# --- 💡 PROXY DE MÍDIA (TURBINADO COM RESGATE VIA BASE64) ---
@router.get("/chat/getBase64FromMediaMessage")
async def media_proxy(
        url: str,
        messageId: str = None,
):
    """
    Proxy inteligente: Tenta URL original. Se falhar, usa o Resgate Evolution (getBase64FromMediaMessage).
    """
    # 1. Decodifica a URL original
    try:
        decoded_url = base64.b64decode(url).decode('utf-8')
        target_url = decoded_url if decoded_url.startswith("http") else url
    except:
        target_url = url

    # 2. Tenta Baixar da URL Original (Método Rápido)
    try:
        async with httpx.AsyncClient(verify=False) as client:
            # Tenta primeiro sem headers (para URLs públicas do whatsapp/s3)
            r = await client.get(target_url, timeout=5.0)

            # Se falhar (401/403), tenta com a API Key (caso seja url interna da evolution)
            if r.status_code != 200:
                headers = {"apikey": EVOLUTION_API_KEY}
                r = await client.get(target_url, headers=headers, timeout=5.0)

            if r.status_code == 200:
                return StreamingResponse(
                    r.aiter_bytes(),
                    media_type=r.headers.get("content-type"),
                    headers={"Cache-Control": "public, max-age=31536000"}
                )
    except Exception as e:
        print_warning(f"⚠️ [Proxy] URL original falhou ({e}). Tentando resgate via Evolution...")

    # 3. PLANO B: Resgate via getBase64FromMediaMessage (O QUE FUNCIONOU NO CURL!)
    if messageId:
        print_info(f"🚑 [Proxy] Resgatando mídia ID: {messageId} via Evolution...")
        try:
            rescue_url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{INSTANCE_NAME}"

            # Payload IDÊNTICO ao seu CURL de sucesso
            payload = {
                "message": {
                    "key": {
                        "id": messageId
                    }
                },
                "convertToMp4": False
            }

            headers = {
                "apikey": EVOLUTION_API_KEY,
                "Content-Type": "application/json"
            }

            async with httpx.AsyncClient() as client:
                res = await client.post(rescue_url, headers=headers, json=payload, timeout=30.0)

                if res.status_code == 200:
                    data = res.json()
                    base64_str = data.get("base64")
                    mimetype = data.get("mimetype")  # Evolution retorna o mime correto!

                    if base64_str:
                        import io
                        # Decodifica o base64 para bytes reais
                        file_bytes = base64.b64decode(base64_str)

                        print_success(f"✅ [Proxy] Mídia {messageId} recuperada com sucesso!")

                        return StreamingResponse(
                            io.BytesIO(file_bytes),
                            media_type=mimetype or "application/octet-stream",
                            headers={"Cache-Control": "public, max-age=31536000"}
                        )
                else:
                    print_error(f"❌ [Proxy] Evolution recusou resgate: {res.text}")

        except Exception as e_rescue:
            print_error(f"❌ [Proxy] Falha crítica no resgate: {e_rescue}")

    # Se tudo falhar
    # Retorna um 404, mas o frontend (CustomAudioPlayer) vai tratar isso exibindo o aviso de erro
    raise HTTPException(status_code=404, detail="Mídia irrecuperável")