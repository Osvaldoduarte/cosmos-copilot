# Em backend/services/conversation_service.py
# (SUBSTITUA O ARQUIVO INTEIRO)

from typing import List, Dict, Any
from fastapi import HTTPException, status, Depends
import traceback

from core.shared import (
    print_error, print_info, print_success, print_warning
)
from repositories.chroma_repository import ChromaConversationsRepository, get_conversations_repository

"""
Esta é a Camada de Serviço (Service Layer).
"""

class ConversationService:
    def __init__(self, repository: ChromaConversationsRepository = Depends(get_conversations_repository)):
        self.repository = repository

    async def get_all_conversations(self, skip: int, limit: int) -> List[Dict[str, Any]]:
        try:
            return await self.repository.list_conversations(skip=skip, limit=limit)
        except Exception as e:
            print_error(f"❌ [Service] Erro ao listar conversas: {e}")
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao listar conversas: {e}"
            )

    async def get_messages_for_conversation(self, contact_id: str) -> List[Dict[str, Any]]:
        if not self.repository:
            raise HTTPException(status_code=503, detail="Repositório Chroma não inicializado.")
        try:
            messages = await self.repository.get_messages_by_contact(contact_id)
            if not messages:
                return []
            return messages
        except Exception as e:
            print_error(f"❌ [Service] Erro ao buscar mensagens: {e}")
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao buscar mensagens: {e}"
            )

    async def save_message_from_webhook(self, message_data: Dict[str, Any]):
        if not self.repository:
            print_error("❌ [Service] Repositório Chroma não inicializado. Mensagem do webhook perdida.")
            return
        try:
            await self.repository.add_message(message_data)
        except Exception as e:
            print_error(f"❌ [Service] Erro ao salvar mensagem do webhook: {e}")
            traceback.print_exc()

    # --- 💡 CORREÇÃO LGPD: MOVIDO PARA DENTRO DA CLASSE 💡 ---
    async def delete_all_conversations(self):
        """
        Solicita ao repositório que apague TODOS os dados da coleção.
        """
        print_warning("🔴 [Service] Solicitando exclusão de TODOS OS DADOS da coleção...")
        if not self.repository:
            print_error("❌ [Service] Repositório não inicializado. Não é possível limpar dados.")
            return
        try:
            # Chama o novo método do repositório
            await self.repository.delete_collection_data()
            print_success("✅ [Service] Todos os dados da coleção foram excluídos.")
        except Exception as e:
            print_error(f"❌ [Service] Falha ao excluir dados da coleção: {e}")
            traceback.print_exc()
            # Não lançamos exceção de volta para o webhook, apenas logamos.


# --- Função Fábrica (Factory) ---
def get_conversation_service(
    service: ConversationService = Depends(ConversationService)
) -> ConversationService:
    """
    Função de Injeção de Dependência (DI) para o Serviço.
    """
    return service