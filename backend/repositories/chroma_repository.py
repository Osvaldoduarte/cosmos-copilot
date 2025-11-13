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
import chromadb.errors  # Importante para capturar o erro específico

from core.shared import print_error, print_info, print_success, print_warning

# --- CONFIGURAÇÃO CHROMA (Variáveis Globais) ---
CHROMA_SERVER_URL = os.getenv("CHROMA_SERVER_URL",
                              "http://localhost:8000")  # Ajustado para padrão local se não houver env
COLLECTION_HISTORY_NAME = os.getenv("CHROMA_COLLECTION", "conversations_v3")
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
            # Pega a URL correta do .env
            url_env = os.getenv("CHROMA_SERVER_URL")

            # Fallback para localhost APENAS se não tiver nada no .env
            if not url_env:
                print_warning("⚠️ [Repo] CHROMA_SERVER_URL não definido. Usando localhost:8000.")
                url_env = "http://localhost:8000"

            # Garante o prefixo para o parser funcionar
            if not url_env.startswith(('http://', 'https://')):
                url_env = 'https://' + url_env

            parsed = urlparse(url_env)

            # Lógica robusta para definir Host e Porta
            host = parsed.netloc.split(':')[0] if parsed.netloc else parsed.path.split(':')[0]
            is_ssl = parsed.scheme == 'https'

            # Se for HTTPS (Cloud Run), força 443. Se não, tenta pegar da URL ou usa 8000.
            if is_ssl:
                port = 443
            else:
                port = parsed.port if parsed.port else 8000

            print_info(f"ℹ️  [Repo] Conectando ao Chroma: {host}:{port} (SSL: {is_ssl})")

            # Configurações extras para evitar erros de versão antiga
            from chromadb.config import Settings

            _client_instance = chromadb.HttpClient(
                host=host,
                ssl=is_ssl,
                port=port,
                settings=Settings(anonymized_telemetry=False)
            )

            # Teste rápido de vida
            _client_instance.heartbeat()
            print_success(f"✅ [Repo] Conexão com ChromaDB ({host}) estabelecida!")

        except Exception as e:
            print_error(f"❌ [Repo] Falha na conexão ChromaDB: {e}")
            raise e
    return _client_instance

async def _safe_chroma_call(
        collection, method_name, *args, **kwargs
):
    """
    Função de segurança para encapsular chamadas assíncronas ao ChromaDB.
    """
    # Se collection for None, não dá para chamar método
    if collection is None:
        raise ValueError("Objeto 'collection' é None. A conexão com o ChromaDB foi perdida?")

    func = getattr(collection, method_name)
    partial_func = functools.partial(func, *args, **kwargs)

    try:
        result = await asyncio.to_thread(partial_func)
        return result
    except Exception as e:
        # Loga o erro, mas deixa quem chamou decidir o que fazer (exceto se for crítico)
        print_error(f"❌ [Repo] Erro em operação no ChromaDB ({method_name}): {e}")
        raise e


# --- REPOSITÓRIO PRINCIPAL ---

class ChromaConversationsRepository:
    """Repositório (Adapter) para interagir com a coleção de conversas no Chroma."""

    def __init__(self, client):
        self.client = client
        self.collection_name = COLLECTION_HISTORY_NAME
        self.collection = None
        self._ensure_collection_sync()  # Garante conexão no inicio

    def _ensure_collection_sync(self):
        """ Tenta obter ou criar a coleção de forma síncrona (para __init__). """
        try:
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            print_success(f"✅ [Repo] Conectado à coleção: {self.collection_name}")
        except Exception as e:
            print_error(f"❌ [Repo] Falha ao conectar à coleção {self.collection_name}: {e}")
            raise

    async def _ensure_collection_async(self):
        """ Recuperação de falha: Recria a referência da coleção se ela sumir. """
        print_warning("⚠️ [Repo] Tentando reconectar à coleção perdida...")
        try:
            self.collection = await asyncio.to_thread(
                self.client.get_or_create_collection,
                name=self.collection_name
            )
            print_success("✅ [Repo] Reconexão bem sucedida!")
        except Exception as e:
            print_error(f"❌ [Repo] Falha fatal na reconexão: {e}")

    async def list_conversations(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        print_info("[Repo] Executando list_conversations...")

        try:
            # Tenta buscar. Se der erro de "Collection not found", tenta reconectar e busca de novo.
            try:
                all_messages = await _safe_chroma_call(
                    self.collection,
                    "get",
                    include=["metadatas", "documents"]
                )
            except (chromadb.errors.NotFoundError, Exception) as e:
                if "does not exist" in str(e) or isinstance(e, chromadb.errors.NotFoundError):
                    await self._ensure_collection_async()
                    all_messages = await _safe_chroma_call(
                        self.collection,
                        "get",
                        include=["metadatas", "documents"]
                    )
                else:
                    raise e

            if not all_messages or not all_messages.get('metadatas'):
                print_warning("[Repo] list_conversations: Nenhum documento encontrado.")
                return []

            # --- LÓGICA DE PROCESSAMENTO ---
            conversations_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
                "id": "",
                "contact_name": None,
                "last_message": "",
                "timestamp": 0,
                "client_name_timestamp": 0,
                "avatar_url": None
            })

            for meta, doc in zip(all_messages['metadatas'], all_messages['documents']):
                contact_id = meta.get("contact_id")
                if not contact_id or not contact_id.endswith("@s.whatsapp.net"):
                    continue

                try:
                    timestamp = int(meta.get("timestamp", 0))
                except (ValueError, TypeError):
                    timestamp = 0

                sender = meta.get("sender")
                current_name = meta.get("pushName")
                current_avatar = meta.get("profilePicUrl")

                if timestamp > conversations_map[contact_id]["timestamp"]:
                    conversations_map[contact_id]["last_message"] = doc
                    conversations_map[contact_id]["timestamp"] = timestamp
                    conversations_map[contact_id]["id"] = contact_id

                if sender == "cliente" and current_name and timestamp >= conversations_map[contact_id][
                    "client_name_timestamp"]:
                    conversations_map[contact_id]["contact_name"] = current_name
                    if current_avatar:
                        conversations_map[contact_id]["avatar_url"] = current_avatar
                    conversations_map[contact_id]["client_name_timestamp"] = timestamp

            conversations_list = []
            for contact_id, convo in conversations_map.items():
                if not convo["contact_name"]:
                    convo["contact_name"] = contact_id.split('@')[0]
                if "client_name_timestamp" in convo:
                    del convo["client_name_timestamp"]
                conversations_list.append(convo)

            conversations_list.sort(key=lambda x: x["timestamp"], reverse=True)
            final_list = conversations_list[skip:skip + limit]

            print_success(f"[Repo] list_conversations: Retornando {len(final_list)} conversas.")
            return final_list

        except Exception as e:
            print_error(f"❌ ERRO CRÍTICO em list_conversations: {e}")
            traceback.print_exc()
            return []

    async def add_message(self, message_data: Dict[str, Any]):
        try:
            doc_id = message_data["message_id"]
            content = message_data["content"]
            metadata = {k: v for k, v in message_data.items() if k not in ["message_id"]}

            metadata["timestamp"] = int(metadata.get("timestamp", time.time()))
            metadata["sender"] = str(metadata.get("sender", "unknown"))
            metadata["contact_id"] = str(metadata.get("contact_id", "unknown"))
            metadata["instance_id"] = str(metadata.get("instance_id", INSTANCE_ID))

            # Tenta adicionar. Se der erro de coleção, reconecta.
            try:
                await _safe_chroma_call(
                    self.collection, "add",
                    documents=[content], metadatas=[metadata], ids=[doc_id]
                )
            except (chromadb.errors.NotFoundError, Exception) as e:
                if "does not exist" in str(e):
                    await self._ensure_collection_async()
                    await _safe_chroma_call(
                        self.collection, "add",
                        documents=[content], metadatas=[metadata], ids=[doc_id]
                    )
                else:
                    raise e

        except Exception as e:
            print_error(f"❌ Falha ao salvar mensagem no RAG: {e}")
            pass

    async def delete_collection_data(self):
        """ Exclui e recria a coleção. """
        print_warning(f"🔴 [Repo] Excluindo coleção: {self.collection_name}...")
        try:
            await _safe_chroma_call(self.client, "delete_collection", name=self.collection_name)
            print_info(f"ℹ️  [Repo] Coleção excluída. Recriando...")

            # Pequeno delay para garantir que o Chroma processou a deleção
            await asyncio.sleep(0.5)

            self.collection = await asyncio.to_thread(
                self.client.get_or_create_collection,
                name=self.collection_name
            )
            print_success(f"✅ [Repo] Coleção recriada com sucesso.")
        except Exception as e:
            print_error(f"❌ [Repo] Falha ao resetar coleção: {e}")
            # Tenta recuperar
            await self._ensure_collection_async()

    async def get_messages_by_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        if not contact_id: return []
        print_info(f"ℹ️  [Repo] get_messages_by_contact: {contact_id}")

        try:
            query_results = await _safe_chroma_call(
                self.collection, "get",
                where={"contact_id": contact_id},
                include=["metadatas", "documents"]
            )

            if not query_results or not query_results.get('ids'):
                return []

            messages_list = []
            for doc_id, meta, doc in zip(query_results['ids'], query_results['metadatas'], query_results['documents']):
                message_obj = {
                    "message_id": doc_id,
                    "content": doc,
                    **meta
                }
                try:
                    message_obj["timestamp"] = int(message_obj.get("timestamp", 0))
                except:
                    message_obj["timestamp"] = 0
                messages_list.append(message_obj)

            messages_list.sort(key=lambda x: x["timestamp"], reverse=False)
            return messages_list

        except Exception as e:
            print_error(f"❌ ERRO em get_messages_by_contact: {e}")
            return []


# --- Singleton ---

def get_conversations_repository() -> ChromaConversationsRepository:
    global _repository_instance
    if _repository_instance is None:
        client = get_chroma_client()
        _repository_instance = ChromaConversationsRepository(client=client)
    return _repository_instance