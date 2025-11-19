import os
import json
import chromadb
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse
import traceback

# IMPORTS ESTÁVEIS (LangChain 0.1.x)
from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:
    from langchain.retrievers.ensemble import EnsembleRetriever

from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
from chromadb.config import Settings
from thefuzz import fuzz

from core.shared import IA_MODELS, print_error, print_info, print_success, print_warning

# --- CONFIGURAÇÕES ---
CORE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = CORE_DIR.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
PLAYBOOK_PATH = str(DATA_DIR / "playbook_vendas.json")
GEMINI_MODEL_NAME = "gemini-2.5-flash"
env_path = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=env_path)


# --- CLASSES DE SAÍDA ---
class AIResponse(BaseModel):
    sugestao_resposta: str = Field(description="A sugestão de resposta para o vendedor enviar.")
    proximo_passo: Optional[str] = Field(description="Uma sugestão de ação ou pergunta futura.")


class StageTransitionDecision(BaseModel):
    proximo_stage_id: str
    justificativa: str


# --- SERVIÇO PRINCIPAL ---
class SalesCopilot:
    def __init__(self, llm, retriever, playbook, embeddings):
        self.llm = llm
        self.retriever = retriever
        self.playbook = playbook
        self.embeddings = embeddings

        self.prompt = ChatPromptTemplate.from_template("""
        Você é o VENAI, um assistente de vendas experiente.

        CONTEXTO DA CONVERSA (Últimas mensagens):
        {history_context}

        MANUAL TÉCNICO / CONHECIMENTO (RAG):
        {tech_context}

        PERGUNTA OU AÇÃO ATUAL DO CLIENTE:
        "{query}"

        OBJETIVO: Ajudar o vendedor a responder de forma persuasiva e técnica.

        Responda ESTRITAMENTE neste formato JSON:
        {{
            "sugestao_resposta": "Texto da resposta...",
            "proximo_passo": "Sugestão do que fazer a seguir (opcional)"
        }}
        """)
        self.chain = self.prompt | self.llm.with_structured_output(AIResponse)

    # 💡 CORREÇÃO AQUI: Argumentos renomeados para bater com o main.py
    def generate_sales_suggestions(self, query, full_conversation_history, current_stage_id, is_private_query,
                                   client_data):
        print_info(f"🤖 [IA] Gerando sugestão para: '{query}'")

        # Usa a variável com o nome novo
        history = full_conversation_history

        # 1. Prepara o Histórico
        recent_msgs = history[-10:] if history else []
        history_text = "\n".join([f"{m.get('sender', '?').upper()}: {m.get('content', '')}" for m in recent_msgs])

        # 2. Busca Conhecimento Técnico (RAG)
        tech_text = "Nenhuma informação técnica encontrada."
        if self.retriever:
            try:
                docs = self.retriever.invoke(query)
                if docs:
                    tech_text = "\n\n".join([d.page_content for d in docs])
                    print_success(f"📚 [IA] Encontrados {len(docs)} documentos técnicos.")
            except Exception as e:
                print_warning(f"⚠️ [IA] Erro no retriever: {e}")

        # 3. Chama o LLM
        try:
            resp = self.chain.invoke({
                "history_context": history_text,
                "tech_context": tech_text,
                "query": query
            })

            return {
                "status": "success",
                "suggestions": {
                    "immediate_answer": resp.sugestao_resposta,
                    "follow_up_options": [
                        {"text": resp.proximo_passo, "is_recommended": True}] if resp.proximo_passo else []
                }
            }
        except Exception as e:
            print_error(f"❌ [IA] Erro ao gerar resposta: {e}")
            traceback.print_exc()
            return {"status": "error", "suggestions": {"immediate_answer": "Erro ao processar IA."}}


# --- FACTORY ---
def initialize_chroma_client():
    url = os.getenv("CHROMA_SERVER_URL")
    if not url: return None
    try:
        if not url.startswith(('http://', 'https://')): url = 'https://' + url
        parsed = urlparse(url)
        is_ssl = parsed.scheme == 'https'
        port = parsed.port or (443 if is_ssl else 8000)

        return chromadb.HttpClient(
            host=parsed.hostname,
            port=port,
            ssl=is_ssl,
            settings=Settings(anonymized_telemetry=False)
        )
    except:
        return None


def load_models(client):
    if not client: return None, None, None, None
    api_key = os.getenv("GEMINI_API_KEY")

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=api_key, temperature=0.2)
    embed = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

    retriever = None
    try:
        db = Chroma(client=client, collection_name="evolution", embedding_function=embed)
        try:
            # Verifica se tem dados
            if db._collection.count() == 0:
                retriever = BM25Retriever.from_documents([Document(page_content="vazio")])
            else:
                # Retriever Híbrido (BM25 + Vetor)
                all_docs = db._collection.get()
                docs_objs = [Document(page_content=t, metadata=m or {}) for t, m in
                             zip(all_docs['documents'], all_docs['metadatas'])]
                bm25 = BM25Retriever.from_documents(docs_objs)
                bm25.k = 3
                chroma_retriever = db.as_retriever(search_kwargs={"k": 3})
                retriever = EnsembleRetriever(retrievers=[bm25, chroma_retriever], weights=[0.4, 0.6])
        except:
            retriever = db.as_retriever()
    except:
        retriever = None

    return llm, retriever, embed, {}


def get_sales_copilot():
    if not IA_MODELS.get("llm"): return None
    return SalesCopilot(IA_MODELS["llm"], IA_MODELS["retriever"], IA_MODELS["playbook"], IA_MODELS["embeddings"])