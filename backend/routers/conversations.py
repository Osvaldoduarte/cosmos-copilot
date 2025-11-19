# Em backend/routers/conversations.py
# (SUBSTITUA O ARQUIVO INTEIRO)

from fastapi import APIRouter, Depends, Query, status, HTTPException, Body, BackgroundTasks
from typing import List, Dict, Any

from core import security
from schemas import User, ConversationListResponse
from services.conversation_service import ConversationService, get_conversation_service
from routers.evolution import SendMessageRequest  # Import para a rota alternativa

# 1. Definição do Router
router = APIRouter(
    prefix="/conversations",
    tags=["Conversas"],
    dependencies=[Depends(security.get_current_active_user)]
)


# Rota 1: Lista todas as conversas
@router.get(
    "/",
    summary="Lista todas as conversas ativas (Do ChromaDB).",
    status_code=status.HTTP_200_OK,
    response_model=ConversationListResponse
)
async def list_conversations(
        service: ConversationService = Depends(get_conversation_service),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000)
) -> ConversationListResponse:
    convo_list = await service.get_all_conversations(
        skip=skip,
        limit=limit
    )
    return {
        "status": "success",
        "conversations": convo_list
    }


# Rota 2: Obter mensagens de uma conversa (CORRIGIDA)
@router.get(
    "/{contact_id}/messages",
    summary="Busca todas as mensagens de uma conversa por JID.",
    status_code=status.HTTP_200_OK
)
async def get_conversation_messages(
        contact_id: str,
        service: ConversationService = Depends(get_conversation_service),
        current_user: User = Depends(security.get_current_active_user)
) -> List[Dict[str, Any]]:
    # 💡 CORREÇÃO CRÍTICA DE ID:
    # Se o frontend mandar só o número, adicionamos o sufixo para bater com o banco.
    if contact_id and "@" not in contact_id:
        print(f"⚠️ [Router] ID sem sufixo recebido ({contact_id}). Adicionando @s.whatsapp.net")
        contact_id = f"{contact_id}@s.whatsapp.net"

    if not contact_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O 'contact_id' (JID) é obrigatório."
        )

    return await service.get_messages_for_conversation(contact_id)


# Rota 3: Marcar como lida
@router.post(
    "/{contact_id}/mark-read",
    summary="Marca uma conversa como lida (Endpoint 'Dummy').",
    status_code=status.HTTP_200_OK
)
async def mark_conversation_as_read(
        contact_id: str,
        service: ConversationService = Depends(get_conversation_service),
        current_user: User = Depends(security.get_current_active_user)
):
    # Stub para evitar 404 no frontend
    return {"status": "ok", "message": "Endpoint 'mark-read' recebido."}


# Rota 4: Rota alternativa de envio (Para compatibilidade com Frontend)
@router.post("/{contact_id}/messages", summary="Rota alternativa de envio")
async def send_message_alternative(
        contact_id: str,
        payload: dict = Body(...),
        background_tasks: BackgroundTasks = None,
        current_user: User = Depends(security.get_current_active_user),
        service: ConversationService = Depends(get_conversation_service)
):
    """
    Captura tentativas de envio feitas para /conversations/{id}/messages
    """
    print(f"🎣 [Rota Alternativa] Frontend tentou enviar para conversations/{contact_id}/messages")

    # Corrige ID se necessário
    if "@" not in contact_id:
        contact_id = f"{contact_id}@s.whatsapp.net"

    texto = payload.get("content") or payload.get("message") or payload.get("text") or ""

    if not texto:
        raise HTTPException(status_code=422, detail="Não foi possível encontrar o texto da mensagem no payload.")

    # Importação tardia para evitar ciclo
    from main import send_whatsapp_message, INSTANCE_NAME
    import time
    import uuid

    # 1. Envia
    sent = await send_whatsapp_message(contact_id, texto)
    if not sent:
        raise HTTPException(status_code=500, detail="Falha no envio Evolution")

    # 2. Salva
    msg_id = f"sent_alt_{uuid.uuid4()}"
    message_obj = {
        "message_id": msg_id,
        "contact_id": contact_id,
        "content": texto,
        "sender": "vendedor",
        "timestamp": int(time.time()),
        "pushName": current_user.full_name or "Vendedor",
        "instance_id": INSTANCE_NAME
    }
    background_tasks.add_task(service.save_message_from_webhook, message_obj)

    return {"status": "success", "message_id": msg_id}