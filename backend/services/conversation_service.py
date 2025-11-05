# Em backend/services/conversation_service.py
# (SUBSTITUA o conteúdo deste arquivo)

import asyncio
from typing import List, Dict, Any
from fastapi import HTTPException, status, Depends

# Importa a CLASSE e a FUNÇÃO FÁBRICA do repositório
from repositories.chroma_repository import ChromaConversationsRepository, get_conversations_repository

"""
Esta é a Camada de Serviço (Service Layer).
"""

class ConversationService:
    # O __init__ (Correto)
    def __init__(self, repository: ChromaConversationsRepository = Depends(get_conversations_repository)):
        """
        Usa Injeção de Dependência (DI) do FastAPI.
        """
        self.repository = repository

    # --- 💡 CORREÇÃO: O MÉTODO QUE FALTAVA ---
    async def get_all_conversations(self, skip: int, limit: int) -> List[Dict[str, Any]]:
        """
        Busca a lista de conversas do repositório.
        Este método estava faltando e causando o AttributeError.
        """
        try:
            # Chama o método 'list_conversations' do repositório
            return await self.repository.list_conversations(skip=skip, limit=limit)
        except ConnectionError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Não foi possível conectar ao Chroma DB: {e}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao listar conversas: {e}"
            )

    # --- 💡 CORREÇÃO: O MÉTODO QUE FALTAVA ---
    async def get_messages_for_conversation(self, contact_id: str) -> List[Dict[str, Any]]:
        """
        Busca mensagens de uma conversa específica do repositório.
        Este método também estava faltando (seria seu próximo erro).
        """
        if not self.repository:
            raise HTTPException(status_code=503, detail="Repositório Chroma não inicializado.")
        try:
            # Chama o método 'get_messages_by_contact' do repositório
            messages = await self.repository.get_messages_by_contact(contact_id)
            if not messages:
                # Retorna lista vazia (correto para o frontend)
                return []
            return messages
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao buscar mensagens: {e}"
            )

    # --- Método de Salvamento (Correto) ---
    async def save_message_from_webhook(self, message_data: Dict[str, Any]):
        """
        Salva uma nova mensagem (vinda do webhook) no repositório.
        """
        if not self.repository:
            print("❌ [Service] Repositório Chroma não inicializado. Mensagem do webhook perdida.")
            return
        try:
            await self.repository.add_message(message_data)
            # print(f"✅ [Service] Mensagem do webhook salva no Chroma.") # (Log reduzido)
        except Exception as e:
            print(f"❌ [Service] Erro ao salvar mensagem do webhook: {e}")


# --- 💡 CORREÇÃO: Função Fábrica (Factory) ---
# (Garante que a Injeção de Dependência funcione)

def get_conversation_service(
    service: ConversationService = Depends(ConversationService)
) -> ConversationService:
    """
    Função de Injeção de Dependência (DI) para o Serviço.
    """
    return service