# Em backend/repositories/chroma_repository.py

import os
import chromadb
import asyncio
import time
import traceback
import functools
from typing import List, Dict, Any
from collections import defaultdict
from fastapi import HTTPException, status
from urllib.parse import urlparse

from core.shared import print_error, print_info, print_success, print_warning

# --- CONFIGURAÇÃO CHROMA (Variáveis Globais) ---
CHROMA_SERVER_URL = os.getenv("CHROMA_SERVER_URL", "https://chroma-server-129644477821.us-central1.run.app")
COLLECTION_HISTORY_NAME = os.getenv("CHROMA_COLLECTION", "conversations_v2")
INSTANCE_ID = os.getenv("EVOLUTION_INSTANCE_NAME", "cosmos-test")

# --- Variável Singleton para o Cliente ---
_client_instance = None
_repository_instance = None


# --- FUNÇÕES AUXILIARES DE INFRA ---

def get_chroma_client():
    """ Retorna a instância singleton do cliente ChromaDB (HttpClient). """
    global _client_instance
    if _client_instance is None:
        try:
            url_to_parse = os.getenv("CHROMA_SERVER_URL", CHROMA_SERVER_URL)
            if not url_to_parse.startswith(('http://', 'https://')):
                url_to_parse = 'https://' + url_to_parse

            parsed_url = urlparse(url_to_parse)
            host = parsed_url.netloc.split(':')[0] if parsed_url.netloc else parsed_url.path.split(':')[0]
            ssl_enabled = parsed_url.scheme == 'https'
            port = parsed_url.port or (443 if ssl_enabled else 80)

            print_info(f"ℹ️  [Repo] Tentando conectar ao Chroma: {host}:{port} (SSL: {ssl_enabled})")

            _client_instance = chromadb.HttpClient(
                host=host,
                ssl=ssl_enabled,
                port=port
            )
            _client_instance.heartbeat()
            print_success(f"✅ ✅ [Repo] Heartbeat com ChromaDB bem-sucedido.")

        except Exception as e:
            print_error(f"❌ ❌ [Repo] Falha na conexão ChromaDB: {e}")
            raise e
    return _client_instance


async def _safe_chroma_call(
        collection, method_name, *args, **kwargs
):
    """
    Função de segurança para encapsular chamadas assíncronas ao ChromaDB,
    tratando a natureza síncrona/assíncrona do cliente.
    """
    func = getattr(collection, method_name)

    # 💡 Usa functools.partial para capturar argumentos e kwargs
    partial_func = functools.partial(func, *args, **kwargs)

    # Executa a chamada síncrona em um executor thread (FastAPI/Asyncio)
    try:
        result = await asyncio.to_thread(partial_func)
        return result
    except Exception as e:
        print_error(f"❌ [Repo] Erro em operação no ChromaDB ({method_name}): {e}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha de comunicação com o banco de dados de histórico: {method_name}"
        )


# --- REPOSITÓRIO PRINCIPAL ---

class ChromaConversationsRepository:
    """Repositório (Adapter) para interagir com a coleção de conversas no Chroma."""

    def __init__(self, client):
        self.client = client

        # ✅ CORREÇÃO: Define o atributo antes de usá-lo
        self.collection_name = COLLECTION_HISTORY_NAME

        try:
            # 1. Garante que a coleção de conversas seja carregada
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            print_success(f"✅ [Repo] Conectado à coleção: {self.collection_name}")

        except Exception as e:
            # 2. Usa o atributo self.collection_name no log de erro
            print_error(f"❌ [Repo] Falha ao conectar à coleção {self.collection_name}: {e}")
            raise  # Propaga o erro fatal de conexão

        self.instance_id = INSTANCE_ID

    async def list_conversations(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retorna a lista de metadados das conversas reais (agrupando mensagens pelo ID do contato).
        """
        print_info("[Repo] Executando list_conversations...")

        try:
            # 1. Busca todos os documentos (MANDATORY DEBUG STEP: SEM FILTRO!)
            # Isso é para provar que as mensagens estão lá e nos dar o metadado correto.
            all_messages = await _safe_chroma_call(
                self.collection,
                "get",
                # where={"instance_id": self.instance_id},  <-- REMOVIDO PERMANENTEMENTE!
                include=["metadatas", "documents"]
            )

            if not all_messages or not all_messages.get('metadatas'):
                print_warning(
                    "[Repo] list_conversations: Nenhum documento encontrado. (Coleção vazia ou erro de busca)")
                return []

            # ✅ DEBUG CRÍTICO: Imprime o primeiro metadado para verificar a chave correta
            print_info(f"✅ DEBUG: ENCONTRADAS {len(all_messages['metadatas'])} MENSAGENS NO TOTAL.")
            print_info(f"✅ DEBUG: Metadados do primeiro documento: {all_messages['metadatas'][0]}")

            # 2. Agrupa as mensagens por contact_id (conversa)
            conversations_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
                "id": "", "instance_id": self.instance_id, "contact_name": "Desconhecido",
                "last_message": "", "status": "open", "timestamp": 0
            })

            VENDOR_PUSH_NAME = "Osvaldo Netto"

            # 3. Itera sobre todas as mensagens e constrói o mapa
            for meta, doc in zip(all_messages['metadatas'], all_messages['documents']):
                contact_id = meta.get("contact_id")

                try:
                    timestamp = int(meta.get("timestamp", time.time()))
                except (ValueError, TypeError):
                    timestamp = 0

                if not contact_id or contact_id == "unknown":
                    continue

                current_message_name = meta.get("pushName") or meta.get("contact_name") or contact_id

                # 💡 Lógica Corrigida para Nome:
                # O nome da conversa só deve ser atualizado se o nome da mensagem atual
                # NÃO FOR O NOME DO VENDEDOR e não for nulo.
                if current_message_name and current_message_name != VENDOR_PUSH_NAME:
                    conversations_map[contact_id]["contact_name"] = current_message_name

                # 💡 Lógica para Última Mensagem:
                # A última mensagem e o timestamp são sempre atualizados, independentemente do remetente.
                if timestamp > conversations_map[contact_id]["timestamp"]:
                    conversations_map[contact_id]["id"] = contact_id
                    conversations_map[contact_id]["last_message"] = doc
                    conversations_map[contact_id]["timestamp"] = timestamp

                    # Fallback: Se o nome do cliente ainda não foi capturado (ainda é 'Desconhecido' ou o JID),
                    # use o ID do contato como fallback.
                    if conversations_map[contact_id]["contact_name"] in ["Desconhecido", contact_id]:
                        conversations_map[contact_id][
                            "contact_name"] = current_message_name if current_message_name != VENDOR_PUSH_NAME else contact_id

            # 4. Converte o mapa de volta para uma lista de conversas e ordena
            conversations_list = list(conversations_map.values())
            conversations_list.sort(key=lambda x: x["timestamp"], reverse=True)

            # 5. Aplica paginação (skip e limit)
            final_list = conversations_list[skip:skip + limit]

            print_success(f"[Repo] list_conversations: Retornando {len(final_list)} conversas com sucesso.")
            return final_list

        except HTTPException:
            raise
        except Exception as e:
            print_error(f"❌ ERRO CRÍTICO em list_conversations: {e}")
            traceback.print_exc()
            return []

    async def add_message(self, message_data: Dict[str, Any]):
        """ Adiciona uma nova mensagem no ChromaDB. """
        # ... (Lógica do add_message permanece a mesma) ...
        try:
            doc_id = message_data["message_id"]
            content = message_data["content"]

            metadata = {k: v for k, v in message_data.items() if k not in ["message_id"]}

            metadata["timestamp"] = int(metadata.get("timestamp", time.time()))
            metadata["sender"] = str(metadata.get("sender", "unknown"))
            metadata["contact_id"] = str(metadata.get("contact_id", "unknown"))
            metadata["instance_id"] = str(metadata.get("instance_id", INSTANCE_ID))

            await _safe_chroma_call(
                self.collection,
                "add",
                documents=[content],
                metadatas=[metadata],
                ids=[doc_id]
            )

        except Exception as e:
            print_error(f"❌ Falha ao salvar mensagem no RAG: {e}")
            pass


# --- Singleton (Correto) ---

def get_conversations_repository() -> ChromaConversationsRepository:
    """ Função de Injeção de Dependência (DI) para o Repositório. """
    global _repository_instance
    if _repository_instance is None:
        try:
            client = get_chroma_client()
            _repository_instance = ChromaConversationsRepository(client=client)
        except Exception as e:
            print_error(f"❌ Falha fatal ao criar Singleton do Repositório: {e}")
            raise e
    return _repository_instance