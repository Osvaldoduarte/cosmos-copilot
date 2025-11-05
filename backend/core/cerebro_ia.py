import os
import json
import chromadb
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse
import traceback

from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field
from chromadb.config import Settings
from thefuzz import fuzz

# 💡 CORREÇÃO: Importa o repositório VERDADEIRO
from repositories.chroma_repository import get_conversations_repository, ChromaConversationsRepository
from core.shared import IA_MODELS, print_error, print_info, print_success, print_warning  # Importa os globais

# --- CONFIGURAÇÕES GLOBAIS ---
CHROMA_CLIENT = None
CORE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = CORE_DIR.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
CHROMA_PATH = str(BACKEND_DIR / "chroma_db_local")
CHROMA_CONVERSAS_PATH = str(BACKEND_DIR / "chroma_db_conversas")
PLAYBOOK_PATH = str(DATA_DIR / "playbook_vendas.json")
GEMINI_MODEL_NAME = "gemini-2.5-flash"
env_path = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=env_path)
if not os.environ.get("GEMINI_API_KEY"):
    print_warning(f"ALERTA: Não foi possível carregar as variáveis do arquivo: {env_path}")
CHROMA_HOST = os.environ.get("CHROMA_HOST")
api_key = os.environ.get("GEMINI_API_KEY")


# --- DEFINIÇÕES DE Pydantic (permanecem as mesmas) ---
class StageTransitionDecision(BaseModel):
    proximo_stage_id: str = Field(
        description="O ID do próximo estágio mais lógico para o qual a conversa deve avançar, escolhido estritamente a partir da lista de 'ROTAS POSSÍVEIS'.")
    justificativa: str = Field(
        description="Uma breve justificativa da sua escolha, referenciando o histórico da conversa.")


class AIResponse(BaseModel):
    sugestao_resposta: str = Field(
        description="A resposta direta e factual para a pergunta técnica do cliente, baseada no CONTEXTO TÉCNICO.")
    proximo_passo: Optional[str] = Field(
        description="Uma pergunta ou sugestão de próximo passo para o vendedor enviar ao cliente, alinhada com o OBJETIVO ESTRATÉGICO.")


class ClientData(BaseModel):
    """Estrutura para armazenar os dados extraídos do cliente."""
    nome: Optional[str] = Field(None, description="O nome do cliente, se mencionado.")
    empresa: Optional[str] = Field(None, description="O nome da empresa do cliente, se mencionada.")
    gerente: Optional[str] = Field(None, description="O nome do gerente ou decisor mencionado pelo cliente.")
    necessidades: Optional[List[str]] = Field(None,
                                              description="Uma lista de dores ou necessidades explícitas do cliente (ex: 'emissão de notas', 'valores de mensalidade').")


# --- Templates e Prompts (permanecem os mesmos) ---
# ... (SUPER_PROMPT_TEMPLATE, TRIAGE_PROMPT_TEMPLATE, STAGE_DECISION_TEMPLATE, CLIENT_DATA_EXTRACTION_TEMPLATE) ...

SUPER_PROMPT_TEMPLATE = """
Você é o "VENAI", um assistente de vendas especialista em IA para o sistema CosmosERP.

Sua missão é analisar o contexto completo de uma interação com o cliente e gerar uma resposta estruturada em JSON.

---
ARQUIVO DO CLIENTE (FATOS CONHECIDOS)
Estes são os dados estruturados que já conhecemos sobre o cliente. Use-os para personalizar sua resposta.
{client_data}
---
CONTEXTO GERAL (CÉREBRO 2 - O HISTÓRICO RELEVANTE)
Este é o histórico recente ou trechos relevantes da conversa. Use-o para entender o que foi dito.
{conversation_history}
---
OBJETIVO ESTRATÉGICO (CÉREBRO 3 - O PLAYBOOK DE VENDAS)
Com base na conversa, o estágio atual da venda é '{stage_name}'. O seu objetivo agora é: '{stage_goal}'.
---
EVIDÊNCIAS TÉCNICAS (CÉREBRO 1 - A BASE DE CONHECIMENTO)
Para responder à pergunta do cliente, utilize estritamente as seguintes informações técnicas sobre o produto. Não invente funcionalidades.
{technical_context}
---

PERGUNTA ATUAL: "{query}"

INSTRUÇÃO CRÍTICA:
- Se a "PERGUNTA ATUAL" for do cliente, seu objetivo é respondê-lo e avançar a venda. Gere 'sugestao_resposta' e 'proximo_passo'.
- Se a "PERGUNTA ATUAL" for uma consulta interna do vendedor (ex: "quem é Cristiano?", "qual o valor?"), seu objetivo é responder APENAS ao vendedor. Use o "ARQUIVO DO CLIENTE" e o "CONTEXTO GERAL" para encontrar a resposta. Gere apenas 'sugestao_resposta' e retorne 'proximo_passo' como nulo.

Baseado em TUDO acima, gere sua resposta.
"""

TRIAGE_PROMPT_TEMPLATE = """
Analise a mensagem do usuário e classifique-a estritamente em uma das seguintes categorias:
'saudacao_inicial', 'resposta_qualificacao', 'pergunta_tecnica', 'escolha_de_opcao', 'pergunta_conversacional', 'comentario_geral'.

Sua resposta deve ser APENAS o nome da categoria correspondente, em minúsculas, sem aspas, espaços extras ou qualquer outra pontuação.

Mensagem do usuário: "{query}"
Categoria:
"""
TRIAGE_PROMPT = ChatPromptTemplate.from_template(TRIAGE_PROMPT_TEMPLATE)

STAGE_DECISION_TEMPLATE = """
Você é o "Gerente de Estágios de Vendas", e sua única tarefa é analisar o contexto e decidir para qual estágio a conversa deve avançar.

---
CONTEXTO GERAL (O CLIENTE E A CONVERSA)
Este é o histórico da conversa. Use-o para entender o ponto de partida e o que levou à pergunta atual.
{conversation_history}
---
ESTÁGIO ATUAL: {current_stage_id}

ROTAS POSSÍVEIS PARA O PRÓXIMO ESTÁGIO:
Abaixo está uma lista de próximos estágios possíveis e as condições para ir para cada um.
Você DEVE escolher o 'proximo_stage_id' estritamente a partir desta lista.
{possible_routes}
---

ÚLTIMA AÇÃO / PERGUNTA: "{query}"

Decida e justifique o próximo 'proximo_stage_id' em formato JSON.
"""
STAGE_DECISION_PROMPT = ChatPromptTemplate.from_template(STAGE_DECISION_TEMPLATE)

CLIENT_DATA_EXTRACTION_TEMPLATE = """
Sua única tarefa é analisar um histórico de conversa e extrair as seguintes informações sobre o cliente: nome, empresa, nome do gerente (se houver) e uma lista de suas necessidades.
Se uma informação não for mencionada, retorne 'null' para aquele campo.

Histórico da Conversa:
{conversation_history}
"""


# --- FUNÇÕES AUXILIARES (Permanecem as mesmas ou são movidas para métodos) ---

def extract_client_data_from_history(llm: ChatGoogleGenerativeAI, conversation_history: str) -> ClientData:
    """
    Usa um LLM para extrair dados estruturados (nome, empresa, etc.) do histórico de uma conversa.
    """
    print_info("🧠 CÉREBRO 2.5: Extraindo dados estruturados do cliente do histórico...")
    try:
        # Monta a cadeia para extração com saída estruturada
        prompt = ChatPromptTemplate.from_template(CLIENT_DATA_EXTRACTION_TEMPLATE)
        chain = prompt | llm.with_structured_output(ClientData)

        # Invoca a cadeia com o histórico
        extracted_data = chain.invoke({"conversation_history": conversation_history})

        print_success(f"✅ CÉREBRO 2.5: Dados extraídos: {extracted_data.dict()}")
        return extracted_data
    except Exception as e:
        print_error(f"❌ ERRO ao extrair dados do cliente: {e}")
        traceback.print_exc()
        # Retorna um objeto vazio em caso de erro
        return ClientData()


def decide_next_stage(llm: ChatGoogleGenerativeAI, conversation_history: str, current_stage_id: str,
                      possible_routes: str, query: str) -> str:
    # (Mantenha esta função auxiliar fora da classe, pois ela não depende de self.retriever ou self.playbook,
    # mas sim do LLM e dos dados de entrada, sendo mais fácil de testar isoladamente.)
    """
    Função dedicada a usar o LLM para determinar o próximo estágio de vendas.
    """
    print_info(f"🔄 CÉREBRO 3: Iniciando tomada de decisão...")
    try:
        # 1. Monta o prompt
        prompt = STAGE_DECISION_PROMPT

        # 2. Constrói a cadeia
        chain = prompt | llm.with_structured_output(StageTransitionDecision)

        # 3. Invoca a cadeia
        decision = chain.invoke({
            "conversation_history": conversation_history,
            "current_stage_id": current_stage_id,
            "possible_routes": possible_routes,
            "query": query
        })

        print_success(f"✅ CÉREBRO 3: Decisão tomada. Próximo ID: {decision.proximo_stage_id}.")
        return decision.proximo_stage_id

    except Exception as e:
        print_error(f"[DEBUG C3] ERRO durante a decisão de estágio: {e}")
        traceback.print_exc()
        print_error(f"❌ ERRO ao decidir o próximo estágio. Retornando estágio atual: {current_stage_id}.")
        return current_stage_id


def get_dynamic_conversation_context(
        conversation_history: List[Dict[str, Any]],
        query: str,
        embedding_function
) -> str:
    # (Esta função auxiliar de RAG em memória continua a mesma)
    """
    Usa uma BUSCA HÍBRIDA MANUAL com FUZZY MATCHING e Semântica para criar o contexto da conversa.
    """
    if not conversation_history: return "Nenhum histórico de conversa fornecido."
    print_info("🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Criando RAG em memória...")

    docs = [Document(page_content=msg["content"], metadata=msg) for msg in conversation_history if msg.get("content")]
    if not docs: return "Nenhum histórico de conversa encontrado."

    # --- LÓGICA DE BUSCA HÍBRIDA MANUAL APRIMORADA ---
    keyword_hits = []
    query_words = {word.lower().strip('.,?!') for word in query.split()}
    similarity_threshold = 85

    for doc in docs:
        doc_words = [word.lower().strip('.,?!') for word in doc.page_content.split()]
        for q_word in query_words:
            if any(fuzz.ratio(q_word, d_word) > similarity_threshold for d_word in doc_words):
                keyword_hits.append(doc);
                break

    print_info(
        f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Encontradas {len(keyword_hits)} mensagens por palavra-chave aproximada.")

    # Busca Semântica
    # Nota: Este é um uso ineficiente do ChromaDB (cria e destrói o DB a cada chamada),
    # mas é necessário para o RAG em memória se você não quiser usar um índice mais complexo como o FAISS.
    db_temp = Chroma.from_documents(docs, embedding_function)
    vector_retriever = db_temp.as_retriever(search_kwargs={"k": 5})
    semantic_hits = vector_retriever.invoke(query)
    print_info(
        f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Encontradas {len(semantic_hits)} mensagens por similaridade semântica.")

    # Combinação e Limpeza
    combined_docs = keyword_hits + semantic_hits
    seen_content = set();
    unique_docs = []
    for doc in combined_docs:
        content_key = doc.page_content.strip()
        if content_key not in seen_content:
            seen_content.add(content_key);
            unique_docs.append(doc)

    print_info(f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Contexto combinado com {len(unique_docs)} mensagens únicas.")

    if not unique_docs:
        print_warning("Nenhum documento relevante encontrado. Usando as 5 últimas mensagens como fallback.")
        unique_docs = docs[-5:]

    unique_docs.sort(key=lambda doc: float(doc.metadata.get('timestamp', 0)))

    formatted_context = "\n".join(
        [f"{doc.metadata.get('sender', 'desconhecido').capitalize()}: {doc.page_content}" for doc in unique_docs])

    return formatted_context


def get_relevant_video_suggestion(ensemble_retriever: EnsembleRetriever, query: str) -> Optional[Dict[str, str]]:
    """
    Busca o documento mais relevante para a query e extrai o link do vídeo de seus metadados.
    (Função mantida para ser chamada pela classe SalesCopilot)
    """
    print_info("🎬 CÉREBRO 4: Buscando sugestão de vídeo...")
    try:
        context_docs = ensemble_retriever.invoke(query, k=1)

        if not context_docs:
            print_error("❌ CÉREBRO 4: Nenhum documento relevante encontrado para vídeo.")
            return None

        doc = context_docs[0]
        metadata = doc.metadata

        video_url = metadata.get("url_video")
        video_title = metadata.get("titulo_video")

        if video_url and video_title and ("youtube.com" in video_url or "youtu.be" in video_url):
            print_success(f"✅ CÉREBRO 4: Vídeo sugerido: {video_title}")
            return {
                "title": video_title,
                "url": video_url
            }
        else:
            print_info("ℹ️ CÉREBRO 4: O documento mais relevante não possui metadados de vídeo ou não é um vídeo.")
            return None

    except Exception as e:
        print_error(f"❌ ERRO ao buscar sugestão de vídeo: {e}")
        return None


# --- CLASSE DE SERVIÇO (DIP/SOLID) ---
class SalesCopilot:
    """
    Serviço principal para orquestrar a lógica de IA, incluindo RAG e chamada ao LLM.
    """

    def __init__(
            self,
            llm: ChatGoogleGenerativeAI,
            retriever: EnsembleRetriever,
            playbook: Dict[str, Any],
            embeddings_model: GoogleGenerativeAIEmbeddings  # Adicionado para uso no RAG de memória
    ):
        """
        Docstring (Google Style):
        Inicializa o Copilot com as dependências da LLM, RAG, Playbook e Embeddings.
        """
        self.llm = llm
        self.retriever = retriever
        self.playbook = playbook
        self.embeddings_model = embeddings_model

        # Cria a Chain de LLM e o Prompt principal uma vez na inicialização (Singleton Pattern para o Prompt)
        self.super_prompt = ChatPromptTemplate.from_template(SUPER_PROMPT_TEMPLATE)
        self.main_chain = self.super_prompt | self.llm.with_structured_output(AIResponse)

    def _get_technical_context(self, query: str) -> str:
        """Busca o contexto técnico via RAG (Cérebro 1)."""
        print_info("📚 CÉREBRO 1: Iniciando busca de contexto técnico (RAG)...")
        context_docs = self.retriever.invoke(query)

        technical_context = "\n\n".join(
            [doc.page_content for doc in context_docs]) or "Nenhum contexto técnico relevante encontrado."

        print_success("📚 CÉREBRO 1: Contexto técnico recuperado.")
        return technical_context

    # ✅ MÉTODO PRINCIPAL REFATORADO
    def generate_sales_suggestions(
            self,
            query: str,
            full_conversation_history: List[Dict[str, Any]],
            current_stage_id: str,
            is_private_query: bool,
            client_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Docstring (Google Style): Gera a sugestão de resposta e o próximo passo para o vendedor.

        Args:
            query: Mensagem mais recente.
            full_conversation_history: Histórico de mensagens completo.
            current_stage_id: ID do estágio atual.
            is_private_query: Se a query é interna do vendedor.
            client_data: Dados estruturados extraídos do cliente.

        Returns:
            Um dicionário contendo o payload de sugestão e o próximo ID de estágio.
        """
        print_info("\n--- INICIANDO FLUXO DE GERAÇÃO ESTRATÉGICO V6.0 (CLASSE DE SERVIÇO) ---")

        # ETAPA 1: Cérebro 2 (Histórico Híbrido)
        conversation_context = get_dynamic_conversation_context(
            full_conversation_history,
            query,
            self.embeddings_model
        )
        print_info(f"🧠 CÉREBRO 2: Contexto híbrido da conversa carregado.")

        # ETAPA 2: Decisão de Estágio (Cérebro 3)
        if is_private_query:
            print_warning("⚡️ ROTA RÁPIDA: Consulta privada do vendedor. Pulando Cérebro 3.")
            stage_name = "Consulta Interna"
            stage_goal = "Responder a uma pergunta do vendedor com base no histórico."
            final_next_stage_id = current_stage_id
        else:
            print_info("🌐 ROTA COMPLETA: Análise de mensagem do cliente. Executando Cérebro 3.")
            if not current_stage_id: current_stage_id = self.playbook["initial_stage"]
            current_stage_info = self.playbook["stages"].get(current_stage_id, {})
            stage_name = current_stage_info.get("name", "Análise Inicial")
            stage_goal = current_stage_info.get("goal", "Responder à dúvida e avançar a conversa.")
            possible_routes = "\n".join(
                [f"- stage_id: {stage['stage_id']}, condition: {stage['condition']}" for stage in
                 current_stage_info.get("possible_next_stages",
                                        [])]) or "Nenhuma rota de próximo estágio definida."
            try:
                final_next_stage_id = decide_next_stage(
                    llm=self.llm, conversation_history=conversation_context,
                    current_stage_id=current_stage_id, possible_routes=possible_routes, query=query
                )
            except Exception as e:
                print_error(f"FALHA NO CÉREBRO 3 (Decisão de Estágio): {e}. Mantendo o estágio atual como fallback.")
                final_next_stage_id = current_stage_id

        # ETAPA 3: Cérebro 1 (RAG Técnico)
        technical_context = self._get_technical_context(query)

        # ETAPA 4: Síntese e Chamada ao LLM (Super Prompt)
        client_data_text = json.dumps(client_data, indent=2,
                                      ensure_ascii=False) if client_data else "Nenhum dado estruturado sobre o cliente foi coletado ainda."
        print_info("🚀 Montando Super Prompt e fazendo a chamada única ao LLM...")

        # Usa a chain pré-construída
        ai_response = self.main_chain.invoke({
            "client_data": client_data_text, "conversation_history": conversation_context,
            "stage_name": stage_name, "stage_goal": stage_goal,
            "technical_context": technical_context, "query": query
        })
        print_success("✅ LLM retornou uma resposta estruturada.")

        # ETAPAS FINAIS (Vídeo e Formatação do Payload)
        video_suggestion = get_relevant_video_suggestion(self.retriever, query)

        suggestion_payload = {"immediate_answer": ai_response.sugestao_resposta, "follow_up_options": []}

        if ai_response.proximo_passo:
            suggestion_payload["follow_up_options"].append({"text": ai_response.proximo_passo, "is_recommended": True})

        if video_suggestion:
            suggestion_payload["video"] = video_suggestion

        return {"status": "success", "new_stage_id": final_next_stage_id, "suggestions": suggestion_payload}


# --- Funções de Inicialização e DI (Singleton/Factory) ---

def initialize_chroma_client():
    # ... (Mantenha a função initialize_chroma_client existente) ...
    """Inicializa e armazena o cliente ChromaDB HttpClient para v1.2.2."""
    global CHROMA_CLIENT
    CHROMA_SERVER_URL = os.environ.get("CHROMA_HOST")

    if CHROMA_CLIENT is None and CHROMA_SERVER_URL:
        print_info(f"Conectando ao ChromaDB v1.2.2 em {CHROMA_SERVER_URL}")
        try:
            if not CHROMA_SERVER_URL.startswith(('http://', 'https://')):
                CHROMA_SERVER_URL = 'https://' + CHROMA_SERVER_URL

            parsed_url = urlparse(CHROMA_SERVER_URL)
            host = parsed_url.netloc.split(':')[0] if parsed_url.netloc else parsed_url.path.split(':')[0]
            ssl_enabled = parsed_url.scheme == 'https'
            port = parsed_url.port or (443 if ssl_enabled else 80)

            if not host:
                raise ValueError("Não foi possível extrair o hostname da CHROMA_HOST URL.")

            print_info(f"Usando HttpClient com host='{host}', port={port}, ssl={ssl_enabled}")

            CHROMA_CLIENT = chromadb.HttpClient(
                host=host,
                ssl=ssl_enabled,
                port=port
            )
            print_info("Testando conexão com heartbeat...")
            CHROMA_CLIENT.heartbeat()
            print_success("ChromaDB Cliente v1.2.2 conectado com sucesso!")

        except Exception as e:
            print_error(f"Falha na conexão ChromaDB v1.2.2: {e}")
            traceback.print_exc()
            return None
    return CHROMA_CLIENT


def load_models(chroma_client_instance) -> tuple:
    # ... (Mantenha a função load_models existente, ela carrega as dependências no IA_MODELS) ...
    """Carrega modelos e inicializa retrievers para v1.2.2 (Substitui AMBAS as versões antigas)"""
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: raise ValueError("ERRO: Chave GEMINI_API_KEY não configurada.")

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL_NAME,
        google_api_key=api_key,
        temperature=0.1
    )

    embeddings_model_langchain = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004",
        google_api_key=api_key
    )

    COLLECTION_NAME = "evolution"

    print_info(f"Conectando LangChain Chroma à collection '{COLLECTION_NAME}'...")
    try:
        db_tecnico = Chroma(
            client=chroma_client_instance,
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings_model_langchain
        )

        native_collection = db_tecnico._collection

        count = native_collection.count()
        print_success(f"Conectado à collection '{COLLECTION_NAME}'. Documentos encontrados: {count}")

        if count == 0:
            raise FileNotFoundError(
                "ERRO: Banco de Dados Técnico (ChromaDB) está vazio. Execute o pipeline de ingestão.")

    except Exception as e:
        print_error(f"Erro ao conectar LangChain Chroma à collection: {e}")
        traceback.print_exc()
        raise

    print_info("Preparando retrievers para Busca Híbrida...")
    all_docs_resp = native_collection.get(include=["metadatas", "documents"])

    if not all_docs_resp or not all_docs_resp.get('documents'):
        raise FileNotFoundError("ERRO: Falha ao buscar documentos da coleção remota.")

    docs_list = [
        Document(page_content=doc, metadata=meta or {})
        for doc, meta in zip(all_docs_resp['documents'], all_docs_resp['metadatas'])
    ]
    print(f"INFO: {len(docs_list)} documentos baixados para o BM25.")

    keyword_retriever = BM25Retriever.from_documents(docs_list)
    keyword_retriever.k = 3

    vector_retriever = db_tecnico.as_retriever(search_kwargs={"k": 3})

    ensemble_retriever = EnsembleRetriever(
        retrievers=[keyword_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )
    print_success("Retriever Híbrido criado")

    if not Path(PLAYBOOK_PATH).exists():
        raise FileNotFoundError(f"Playbook não encontrado em {PLAYBOOK_PATH}")
    with open(PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
        playbook = json.load(f)

    print_success("LLM, Embedding, DB Técnico e Playbook carregados")
    return llm, ensemble_retriever, embeddings_model_langchain, playbook


# --- FUNÇÃO DE FÁBRICA (FACTORY/DI) ---
def get_sales_copilot() -> SalesCopilot:
    """
    Função de Injeção de Dependência que atua como Singleton/Factory.
    Retorna uma instância de SalesCopilot usando os modelos globais.
    """
    # Verifica se os modelos globais foram carregados pelo main.py
    if IA_MODELS["llm"] is None or IA_MODELS["retriever"] is None or IA_MODELS["playbook"] is None or IA_MODELS[
        "embeddings"] is None:
        raise RuntimeError("Modelos de IA não inicializados. Verifique se o main.py chamou init_models().")

    # Retorna a instância da classe de serviço (o estado do serviço está contido nela)
    return SalesCopilot(
        llm=IA_MODELS["llm"],
        retriever=IA_MODELS["retriever"],
        playbook=IA_MODELS["playbook"],
        embeddings_model=IA_MODELS["embeddings"]
    )