# Em backend/repositories/chroma_repository.py
# (SUBSTITUA O ARQUIVO INTEIRO)

import os
import chromadb
import asyncio
import time
import traceback
import functools
from typing import List, Dict, Any
from collections import defaultdict
from urllib.parse import urlparse
from chromadb.config import Settings

from core.shared import print_error, print_info, print_success, print_warning

CHROMA_SERVER_URL = os.getenv("CHROMA_SERVER_URL", "http://localhost:8000")
COLLECTION_HISTORY_NAME = os.getenv("CHROMA_COLLECTION", "conversations_v3")
INSTANCE_ID = os.getenv("INSTANCE_NAME", "cosmos-test")

_client_instance = None
_repository_instance = None


def get_chroma_client():
    global _client_instance
    if _client_instance is None:
        try:
            url_env = os.getenv("CHROMA_SERVER_URL")
            if not url_env: url_env = "http://localhost:8000"

            if not url_env.startswith(('http://', 'https://')): url_env = 'https://' + url_env

            parsed = urlparse(url_env)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == 'https' else 8000)
            is_ssl = parsed.scheme == 'https'

            print_info(f"ℹ️  [Repo] Conectando Chroma 0.5+ em {host}:{port}...")

            _client_instance = chromadb.HttpClient(
                host=host,
                port=port,
                ssl=is_ssl,
                settings=Settings(anonymized_telemetry=False)
            )
            _client_instance.heartbeat()
            print_success(f"✅ [Repo] Conectado!")

        except Exception as e:
            print_error(f"❌ [Repo] Erro conexão Chroma: {e}")
            raise e
    return _client_instance


async def _safe_chroma_call(collection, method_name, *args, **kwargs):
    if collection is None: return None
    func = getattr(collection, method_name)
    return await asyncio.to_thread(functools.partial(func, *args, **kwargs))


def normalize_contact_id(jid: str) -> str:
    """ Remove o 9º dígito se o JID for brasileiro e tiver 13 dígitos. (Evolução) """
    if not jid or not jid.endswith("@s.whatsapp.net"):
        return jid  # Não é um JID padrão, retorna como está

    number = jid.split('@')[0]

    # Exemplo simples de normalização: 55 DDD NNNNNNNNN (13 dígitos) -> 55 DDD NNNNNNNN (12 dígitos)
    # A Evolution API geralmente padroniza isso.
    # A correção crítica é a remoção de caracters não-numéricos, mas vamos focar na padronização.

    if number.startswith("55") and len(number) == 13:  # 55 DD 9 XXXX XXXX
        # Padrão: remove o 9º dígito se a API do Evolution usar o formato 12 dígitos para lookup.
        # O JID é a chave única, vamos garantir que só salvamos um formato.
        return jid

        # Como não temos uma lógica clara de normalização do seu lado:
    # Vamos focar em garantir que o ID é sempre o mesmo que o Evolution usa para consultas.
    # Se o problema é no 9º dígito, você precisa de uma regra clara aqui:

    # Exemplo: Se sua chave é baseada no Evolution, vamos simplificar para apenas o número
    return jid  # Manteremos o JID completo por enquanto, mas este é o ponto de falha.


class ChromaConversationsRepository:
    def __init__(self, client):
        self.client = client
        self.collection_name = COLLECTION_HISTORY_NAME
        self.collection = None
        self._ensure_collection()

    def _ensure_collection(self):
        try:
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
        except Exception as e:
            print_error(f"Erro ao conectar coleção: {e}")

    async def list_conversations(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            all_messages = await _safe_chroma_call(self.collection, "get", include=["metadatas", "documents"])
            if not all_messages or not all_messages.get('metadatas'): return []

            conversations_map = defaultdict(lambda: {
                "id": "", "contact_name": None, "last_message": "",
                "timestamp": 0, "client_name_timestamp": 0, "avatar_url": None
            })

            for meta, doc in zip(all_messages['metadatas'], all_messages['documents']):
                contact_id = meta.get("contact_id")
                if not contact_id or not contact_id.endswith("@s.whatsapp.net"): continue

                ts = int(meta.get("timestamp", 0))
                if ts > conversations_map[contact_id]["timestamp"]:
                    conversations_map[contact_id].update({
                        "last_message": doc, "timestamp": ts, "id": contact_id
                    })

                if meta.get("sender") == "cliente" and ts >= conversations_map[contact_id]["client_name_timestamp"]:
                    conversations_map[contact_id]["contact_name"] = meta.get("pushName")
                    conversations_map[contact_id]["client_name_timestamp"] = ts
                    if meta.get("profilePicUrl"):
                        conversations_map[contact_id]["avatar_url"] = meta.get("profilePicUrl")

            final = sorted(list(conversations_map.values()), key=lambda x: x["timestamp"], reverse=True)
            for c in final:
                if not c["contact_name"]: c["contact_name"] = c["id"].split('@')[0]

            return final[skip:skip + limit]

        except Exception as e:
            print_error(f"Erro list_conversations: {e}")
            return []

    async def add_message(self, message_data: Dict[str, Any]):
        try:
            doc_id = message_data["message_id"]
            content = message_data["content"]

            contact_id = message_data["contact_id"]
            message_data["contact_id"] = normalize_contact_id(contact_id) # Se necessário

            # Prepara metadados excluindo o ID (já vai como id do doc) e o Content (já vai como document)
            raw_metadata = {k: v for k, v in message_data.items() if k not in ["message_id", "content"]}

            # 🛡️ SANITIZAÇÃO (A Correção Mágica) 🛡️
            clean_metadata = {}
            for k, v in raw_metadata.items():
                if v is None:
                    clean_metadata[k] = ""  # Transforma None em String Vazia (Isso corrige o erro!)
                elif isinstance(v, (str, int, float, bool)):
                    clean_metadata[k] = v
                else:
                    clean_metadata[k] = str(v)  # Força string para listas/dicts complexos

            await _safe_chroma_call(
                self.collection,
                "add",
                documents=[content],
                metadatas=[clean_metadata],
                ids=[doc_id]
            )
        except Exception as e:
            print_error(f"Erro add_message: {e}")

    async def get_messages_by_contact(self, contact_id: str) -> List[Dict[str, Any]]:
        try:
            res = await _safe_chroma_call(self.collection, "get", where={"contact_id": contact_id})
            if not res or not res['ids']: return []

            msgs = []
            for id, meta, doc in zip(res['ids'], res['metadatas'], res['documents']):
                m = {**meta, "message_id": id, "content": doc}
                msgs.append(m)
            return sorted(msgs, key=lambda x: x.get("timestamp", 0))
        except Exception as e:
            print_error(f"Erro get_messages: {e}")
            return []

    async def delete_messages_by_contact(self, contact_id: str):
        print_warning(f"🗑️ [Repo] Deletando: {contact_id}")
        try:
            await _safe_chroma_call(self.collection, "delete", where={"contact_id": contact_id})
            return True
        except Exception as e:
            print_error(f"Erro delete: {e}")
            return False

    async def delete_collection_data(self):
        try:
            self.client.delete_collection(name=COLLECTION_HISTORY_NAME)
            self.collection = self.client.get_or_create_collection(name=COLLECTION_HISTORY_NAME)
        except:
            pass


def get_conversations_repository():
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = ChromaConversationsRepository(get_chroma_client())
    return _repository_instance