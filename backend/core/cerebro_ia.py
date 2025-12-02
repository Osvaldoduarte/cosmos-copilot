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


class SalesContextResponse(BaseModel):
    summary: str = Field(description="Resumo curto da negociação até agora.")
    sentiment: str = Field(description="Sentimento do cliente (Positivo, Neutro, Negativo, Irritado, Interessado).")
    stage: str = Field(description="Etapa atual do funil (Ex: Prospecção, Qualificação, Proposta, Negociação, Fechamento).")
    next_step: str = Field(description="O próximo passo lógico para avançar a venda.")
    advice: str = Field(description="Conselho estratégico para o vendedor (o que evitar, o que focar).")


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

        # Prompt para Análise de Contexto
        self.context_prompt = ChatPromptTemplate.from_template("""
        Você é um Gerente de Vendas Sênior analisando uma conversa.

        HISTÓRICO DA CONVERSA:
        {history_context}

        OBJETIVO: Analisar a situação atual e orientar o vendedor.

        Responda ESTRITAMENTE neste formato JSON:
        {{
            "summary": "Resumo de 1 frase sobre o que está acontecendo.",
            "sentiment": "Sentimento do cliente",
            "stage": "Etapa do funil",
            "next_step": "Ação recomendada",
            "advice": "Conselho tático para o vendedor (ex: 'Cuidado, ele parece impaciente' ou 'Foque no benefício X')"
        }}
        """)
        self.context_chain = self.context_prompt | self.llm.with_structured_output(SalesContextResponse)

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
            if is_private_query:
                # Prompt Específico para Consultas Internas
                internal_prompt = ChatPromptTemplate.from_template("""
                Você é o VENAI, um assistente sênior de vendas.
                
                CONTEXTO DA CONVERSA (Últimas mensagens):
                {history_context}
                
                CONTEXTO TÉCNICO (RAG):
                {tech_context}
                
                PERGUNTA DO VENDEDOR:
                "{query}"
                
                OBJETIVO: Responder a dúvida do vendedor de forma direta, técnica e informativa.
                Use o histórico da conversa para entender o contexto da pergunta.
                NÃO sugira uma resposta para o cliente.
                NÃO sugira próximos passos.
                Apenas responda a pergunta.
                
                Responda ESTRITAMENTE neste formato JSON:
                {{
                    "sugestao_resposta": "Sua resposta informativa para o vendedor...",
                    "proximo_passo": null
                }}
                """)
                chain = internal_prompt | self.llm.with_structured_output(AIResponse)
                resp = chain.invoke({
                    "history_context": history_text,
                    "tech_context": tech_text,
                    "query": query
                })
            else:
                # Prompt Padrão (Sugestão de Resposta)
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

    def analyze_sales_context(self, full_conversation_history):
        print_info(f"🤖 [IA] Analisando contexto de vendas...")
        
        history = full_conversation_history
        # Pega mais contexto para análise (20 msgs)
        recent_msgs = history[-20:] if history else []
        history_text = "\n".join([f"{m.get('sender', '?').upper()}: {m.get('content', '')}" for m in recent_msgs])
        
        try:
            resp = self.context_chain.invoke({
                "history_context": history_text
            })
            
            return {
                "status": "success",
                "analysis": resp.dict()
            }
        except Exception as e:
            print_error(f"❌ [IA] Erro ao analisar contexto: {e}")
            return {"status": "error", "analysis": None}


# --- FACTORY ---
def initialize_chroma_client():
    """
    Inicializa cliente Chroma LOCAL (PersistentClient).
    Não usa mais servidor HTTP remoto.
    """
    try:
        # Define o diretório de persistência
        persist_dir = str(DATA_DIR / "chroma_db")
        print_info(f"🔗 [IA] Inicializando Chroma LOCAL em: {persist_dir}")
        
        client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Testa listando collections
        collections = client.list_collections()
        print_success(f"✅ [IA] Chroma LOCAL inicializado! Collections: {[c.name for c in collections]}")
        return client
    except Exception as e:
        print_error(f"❌ [IA] Erro ao inicializar Chroma LOCAL: {e}")
        traceback.print_exc()
        return None


def load_models(client):
    if not client:
        print_warning("⚠️ [IA] Cliente Chroma não disponível, pulando carregamento de modelos")
        return None, None, None, None
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print_error("❌ [IA] GEMINI_API_KEY não configurada no .env")
        return None, None, None, None

    try:
        print_info("🤖 [IA] Inicializando LLM Gemini...")
        llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=api_key, temperature=0.2)
        print_success(f"✅ [IA] LLM {GEMINI_MODEL_NAME} carregado")
    except Exception as e:
        print_error(f"❌ [IA] Erro ao carregar LLM: {e}")
        return None, None, None, None

    try:
        print_info("📝 [IA] Inicializando Embeddings...")
        embed = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
        print_success("✅ [IA] Embeddings carregados")
    except Exception as e:
        print_error(f"❌ [IA] Erro ao carregar Embeddings: {e}")
        return llm, None, None, None

    retriever = None
    try:
        print_info("🔍 [IA] Configurando Retriever...")
        db = Chroma(client=client, collection_name="evolution", embedding_function=embed)
        try:
            # Verifica se tem dados
            count = db._collection.count()
            print_info(f"📊 [IA] Collection 'evolution' tem {count} documentos")
            
            if count == 0:
                print_warning("⚠️ [IA] Collection vazia, usando BM25 com documento placeholder")
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
                print_success("✅ [IA] Retriever Híbrido (BM25 + Vetor) configurado")
        except Exception as e:
            print_warning(f"⚠️ [IA] Erro ao criar retriever híbrido, usando fallback: {e}")
            retriever = db.as_retriever()
    except Exception as e:
        print_error(f"❌ [IA] Erro ao configurar Retriever: {e}")
        retriever = None

    return llm, retriever, embed, {}


def get_sales_copilot():
    if not IA_MODELS.get("llm"): return None
    return SalesCopilot(IA_MODELS["llm"], IA_MODELS["retriever"], IA_MODELS["playbook"], IA_MODELS["embeddings"])