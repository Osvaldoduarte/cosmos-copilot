# Em backend/routers/conversations.py
# (SUBSTITUA o conteúdo deste arquivo)

from fastapi import APIRouter, Depends, Query, status, HTTPException
from typing import List, Dict, Any

from core import security
# 💡 Importa os schemas e serviços corretos
from schemas import User, ConversationListResponse
from services.conversation_service import ConversationService, get_conversation_service

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
    response_model=ConversationListResponse  # Usa o modelo de resposta correto
)
async def list_conversations(
        service: ConversationService = Depends(get_conversation_service),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000)
) -> ConversationListResponse:
    """
    Endpoint que busca a lista de conversas e as envelopa
    conforme o frontend (useChatData.js) espera.
    """
    convo_list = await service.get_all_conversations(
        skip=skip,
        limit=limit
    )

    # Envelopa a resposta para o Contrato de API do frontend
    return {
        "status": "success",
        "conversations": convo_list
    }


# Rota 2: Obter mensagens de uma conversa
@router.get(
    "/{contact_id}/messages",
    summary="Busca todas as mensagens de uma conversa por JID.",
    status_code=status.HTTP_200_OK
)
async def get_conversation_messages(
        contact_id: str,
        service: ConversationService = Depends(get_conversation_service),
        current_user: User = Depends(security.get_current_active_user)
) -> List[Dict[str, Any]]:  # Retorna uma Lista
    """
    Recupera todas as mensagens de uma conversa.
    Se não houver mensagens, retorna uma lista vazia [].
    """
    if not contact_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O 'contact_id' (JID) é obrigatório."
        )
    return await service.get_messages_for_conversation(contact_id)


# --- 💡 CORREÇÃO: O ENDPOINT QUE FALTAVA (CAUSA DO 404) ---
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
    """
    Endpoint 'stub' (provisório) que o frontend (useChatData.js)
    chama quando um chat é selecionado.

    Ele estava faltando, causando o 404 Not Found.

    Retorna 200 OK para que o frontend possa prosseguir e
    chamar a rota GET /{contact_id}/messages.
    """
    print(f"ℹ️  [Router] Conversa {contact_id} marcada como lida (Ação de UI).")

    # (Em uma V2, chamaríamos: await service.mark_as_read(contact_id))

    return {"status": "ok", "message": "Endpoint 'mark-read' recebido."}