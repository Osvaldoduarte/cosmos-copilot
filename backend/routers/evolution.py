# Em backend/routers/evolution.py
# (SUBSTITUA O ARQUIVO INTEIRO POR ESTE)

import httpx
import os
import traceback
import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from pydantic import BaseModel

from core.security import get_current_active_user, get_current_user
from schemas import UserInDB, User

from services.conversation_service import ConversationService, get_conversation_service
from core.shared import print_error, print_warning, print_success, print_info

from core import security

# --- FIM DAS NOVAS IMPORTAÇÕES ---


router = APIRouter(
    prefix="/evolution",
    tags=["Evolution API Proxy"],
    dependencies=[Depends(get_current_active_user)]
)

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "https://evolution-api-129644477821.us-central1.run.app")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
INSTANCE_NAME = os.getenv("INSTANCE_NAME", "cosmos-test")

if not EVOLUTION_API_KEY:
    raise RuntimeError("EVOLUTION_API_KEY não está configurada nas variáveis de ambiente.")


# --- Schema (Body da Requisição de Envio) ---
class SendMessageRequest(BaseModel):
    recipient_jid: str
    message_text: str


# --- Fim do Schema ---


# --- Endpoints de Proxy ---

@router.post("/instance/create_and_get_qr")
async def proxy_get_qr_code(
        request: Request,
        current_user: UserInDB = Depends(get_current_user)
):
    """ Faz proxy para OBTER O QR CODE de uma instância existente. """
    try:
        try:
            frontend_body = await request.json()
        except Exception:
            frontend_body = {}

        instance_name = frontend_body.get("instanceName") or INSTANCE_NAME
        api_url = f"{EVOLUTION_API_URL}/instance/connect/{instance_name}"
        headers = {"apikey": EVOLUTION_API_KEY}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                api_url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        print_error(f"Proxy (get_qr): Erro de Status da API ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro na Evolution API: {e.response.text}"
        )
    except Exception as e:
        print_error(f"Proxy (get_qr): Erro interno inesperado: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno no proxy: {repr(e)}"
        )


@router.get("/instance/status")
async def proxy_instance_status(
        request: Request,
        current_user: UserInDB = Depends(get_current_user)
):
    """ Faz proxy da verificação de status da instância para a Evolution API. """
    instance_name = request.query_params.get('instanceName') or INSTANCE_NAME

    if not instance_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O parâmetro 'instanceName' é obrigatório."
        )

    api_url = f"{EVOLUTION_API_URL}/instance/connectionState/{instance_name}"
    headers = {"apikey": EVOLUTION_API_KEY}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(api_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as e:
        print_error(f"Proxy (status): Erro de Status da API ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro na Evolution API: {e.response.text}"
        )
    except Exception as e:
        print_error(f"Proxy (status): Erro interno inesperado: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno no proxy: {repr(e)}"
        )


# --- 💡 --- O ENDPOINT DE ENVIO QUE FALTAVA (E CORRIGIDO) --- 💡 ---
@router.post(
    "/message/send",
    summary="Envia uma mensagem de texto e salva no histórico."
)
async def proxy_send_message(
        request_data: SendMessageRequest,  # Recebe o JID e o texto
        background_tasks: BackgroundTasks,  # Para salvar no DB
        current_user: User = Depends(security.get_current_active_user),
        # 💡 CORREÇÃO: Pega o serviço por Injeção de Dependência
        service: ConversationService = Depends(get_conversation_service)
):
    """
    1. Envia a mensagem para a Evolution API.
    2. Salva a mensagem enviada (vendedor) no ChromaDB.
    """
    api_url = f"{EVOLUTION_API_URL}/message/sendText/{INSTANCE_NAME}"
    headers = {"apikey": EVOLUTION_API_KEY, "Content-Type": "application/json"}

    payload = {
        "number": request_data.recipient_jid.split('@')[0],
        "options": {"delay": 1200, "presence": "composing"},
        "textMessage": {"text": request_data.message_text}
    }

    try:
        # 1. Tenta enviar a mensagem pela Evolution API
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, headers=headers, json=payload, timeout=30.0)
            response.raise_for_status()

            response_data = response.json()
            message_id_from_api = response_data.get("key", {}).get("id", f"seller_{uuid.uuid4()}")

        # 2. Se o envio deu certo, salva a mensagem no nosso ChromaDB
        message_obj = {
            "message_id": message_id_from_api,
            "contact_id": request_data.recipient_jid,
            "content": request_data.message_text,
            "sender": "vendedor",
            "timestamp": int(time.time()),
            "pushName": current_user.full_name or "Vendedor",
            "instance_id": INSTANCE_NAME
        }

        # 💡 CORREÇÃO: Chama o método do serviço diretamente
        background_tasks.add_task(service.save_message_from_webhook, message_obj)

        print_success(f"✅ [Proxy Send] Mensagem enviada e salva no DB: {message_id_from_api}")
        return response_data

    except httpx.HTTPStatusError as e:
        print_error(f"Proxy (send): Erro de Status da API ({e.response.status_code}): {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Erro na Evolution API: {e.response.text}"
        )
    except Exception as e:
        print_error(f"Proxy (send): Erro interno inesperado: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno no proxy: {repr(e)}"
        )