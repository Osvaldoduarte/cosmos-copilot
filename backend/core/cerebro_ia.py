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
from langchain_community.retrievers import BM25Retriever # Corrigido conforme aviso
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel, Field

from chromadb.config import Settings

from thefuzz import fuzz


# --- CONFIGURAÇÕES GLOBAIS ---

CHROMA_CLIENT = None
CORE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = CORE_DIR.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
CHROMA_PATH = str(BACKEND_DIR / "chroma_db_local")
CHROMA_CONVERSAS_PATH = str(BACKEND_DIR / "chroma_db_conversas")
PLAYBOOK_PATH = str(DATA_DIR / "playbook_vendas.json")
GEMINI_MODEL_NAME = "gemini-2.5-flash-lite"

env_path = BACKEND_DIR / ".env"

# Carrega as variáveis de ambiente a partir desse caminho
load_dotenv(dotenv_path=env_path)

# Verifica se o arquivo foi realmente carregado (opcional, para debug)
if not os.environ.get("GEMINI_API_KEY"):
    print(f"ALERTA: Não foi possível carregar as variáveis do arquivo: {env_path}")

# --- NOVA LÓGICA DE CONEXÃO AO CHROMA DB ---
CHROMA_HOST = os.environ.get("CHROMA_HOST")
api_key = os.environ.get("GEMINI_API_KEY")

class Colors:
    RED = '\033[91m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    END = '\033[0m'

def print_error(msg): print(f"{Colors.RED}❌ {msg}{Colors.END}")
def print_info(msg): print(f"{Colors.BLUE}ℹ️  {msg}{Colors.END}")
def print_success(msg): print(f"{Colors.GREEN}✅ {msg}{Colors.END}")
def print_warning(msg): print(f"{Colors.YELLOW}⚠️  {msg}{Colors.END}")


def initialize_chroma_client():
    """Inicializa e armazena o cliente ChromaDB HttpClient para v1.2.2."""
    global CHROMA_CLIENT
    CHROMA_URL = os.environ.get("CHROMA_HOST") # URL completa: https://...

    if CHROMA_CLIENT is None and CHROMA_URL:
        print_info(f"Conectando ao ChromaDB v1.2.2 em {CHROMA_URL}")
        try:
            # Extrai apenas o host da URL para o parâmetro 'host'
            parsed_url = urlparse(CHROMA_URL)
            host_name = parsed_url.netloc # Ex: chroma-server-....run.app (sem https://)
            ssl_enabled = parsed_url.scheme == 'https'

            if not host_name:
                 raise ValueError("Não foi possível extrair o hostname da CHROMA_HOST URL.")

            print_info(f"Usando HttpClient com host='{host_name}', ssl={ssl_enabled}")

            # Para ChromaDB v1.x, HttpClient usa host (sem https://) e ssl
            CHROMA_CLIENT = chromadb.HttpClient(
                host=host_name,
                ssl=ssl_enabled
                # port=443 # Omitir a porta é o padrão para ssl=True
            )
            print_info("Testando conexão com heartbeat...")
            CHROMA_CLIENT.heartbeat()
            print_success("ChromaDB Cliente v1.2.2 conectado com sucesso!")

        except Exception as e:
            print_error(f"Falha na conexão ChromaDB v1.2.2: {e}")
            traceback.print_exc()
            return None
    return CHROMA_CLIENT


def load_models(chroma_client_instance) -> tuple:  # Recebe a instância conectada
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

    # Conecta à collection remota usando LangChain Chroma wrapper e o HttpClient
    print_info(f"Conectando LangChain Chroma à collection '{COLLECTION_NAME}'...")
    try:
        # Passa o cliente HttpClient já conectado
        db_tecnico = Chroma(
            client=chroma_client_instance,  # USA O CLIENTE JÁ CONECTADO!
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings_model_langchain  # Langchain usa sua própria func
        )

        # Acessa a coleção nativa subjacente para operações
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

    # Inicializa retrievers
    print_info("Preparando retrievers para Busca Híbrida...")

    # Busca os documentos usando o método nativo (mais confiável)
    all_docs_resp = native_collection.get(include=["metadatas", "documents"])

    if not all_docs_resp or not all_docs_resp.get('documents'):
        raise FileNotFoundError("ERRO: Falha ao buscar documentos da coleção remota.")

    docs_list = [
        Document(page_content=doc, metadata=meta or {})  # Garante que metadata não seja None
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

    # Carrega playbook
    if not Path(PLAYBOOK_PATH).exists():
        raise FileNotFoundError(f"Playbook não encontrado em {PLAYBOOK_PATH}")
    with open(PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
        playbook = json.load(f)

    print_success("LLM, Embedding, DB Técnico e Playbook carregados")
    return llm, ensemble_retriever, embeddings_model_langchain, playbook
if not api_key:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")

# Inicializa o modelo de embeddings que será usado em ambos os casos
embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)


# --- DEFINIÇÃO DA ESTRUTURA DE SAÍDA ---
class StageTransitionDecision(BaseModel):
    proximo_stage_id: str = Field(description="O ID do próximo estágio mais lógico para o qual a conversa deve avançar, escolhido estritamente a partir da lista de 'ROTAS POSSÍVEIS'.")
    justificativa: str = Field(description="Uma breve justificativa da sua escolha, referenciando o histórico da conversa.")

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
    necessidades: Optional[List[str]] = Field(None, description="Uma lista de dores ou necessidades explícitas do cliente (ex: 'emissão de notas', 'valores de mensalidade').")

# --- TEMPLATE DO NOVO SUPER PROMPT ---
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

# --- PROMPTS AUXILIARES ---
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

# --- FUNÇÕES AUXILIARES ---

def extract_client_data_from_history(llm: ChatGoogleGenerativeAI, conversation_history: str) -> ClientData:
    """
    Usa um LLM para extrair dados estruturados (nome, empresa, etc.) do histórico de uma conversa.
    """
    print("🧠 CÉREBRO 2.5: Extraindo dados estruturados do cliente do histórico...")
    try:
        # Monta a cadeia para extração com saída estruturada
        prompt = ChatPromptTemplate.from_template(CLIENT_DATA_EXTRACTION_TEMPLATE)
        chain = prompt | llm.with_structured_output(ClientData)

        # Invoca a cadeia com o histórico
        extracted_data = chain.invoke({"conversation_history": conversation_history})

        print(f"✅ CÉREBRO 2.5: Dados extraídos: {extracted_data.dict()}")
        return extracted_data
    except Exception as e:
        print(f"❌ ERRO ao extrair dados do cliente: {e}")
        # Retorna um objeto vazio em caso de erro
        return ClientData()

def get_or_create_conversation_db(conversation_id: str, embedding_function) -> Chroma:
    persist_directory = os.path.join(CHROMA_CONVERSAS_PATH, f"convo_{conversation_id}")
    return Chroma(persist_directory=persist_directory, embedding_function=embedding_function)


def add_message_to_conversation_rag(db: Chroma, conversation_id: str, message_data: Dict[str, Any]):
    content = message_data.get("content", "")
    if not content: return
    metadata = {"conversation_id": conversation_id, "sender": message_data.get("sender"),
                "timestamp": str(message_data.get("timestamp")), }
    doc_id = message_data.get("message_id")
    db.add_documents([Document(page_content=content, metadata=metadata)], ids=[doc_id] if doc_id else None)
    print(f"INFO: Mensagem adicionada ao RAG da conversa '{conversation_id}'.")


def get_intent_from_query(llm: ChatGoogleGenerativeAI, query: str, prompt_template) -> str:
    """
    Classifica a intenção da mensagem do cliente usando o LLM.
    """
    try:
        # A cadeia agora retorna a string limpa devido às instruções do prompt
        chain = prompt_template | llm | StrOutputParser()
        intent = chain.invoke({"query": query})

        # Faz uma limpeza final e padronização por segurança, embora o prompt instrua a IA a ser estrita
        return intent.strip().lower().replace("'", "").replace('"', '')
    except Exception as e:
        print(f"❌ ERRO ao classificar intenção: {e}")
        # Retorna a intenção mais segura em caso de falha de IA.
        return "comentario_geral"  # Ou "pergunta_conversacional"


def decide_next_stage(llm: ChatGoogleGenerativeAI, conversation_history: str, current_stage_id: str,
                      possible_routes: str, query: str) -> str:
    """
    Função dedicada a usar o LLM para determinar o próximo estágio de vendas.
    Inclui prints de depuração detalhados.
    Retorna o ID do próximo estágio ou o estágio atual em caso de falha.
    """
    print(f"🔄 CÉREBRO 3: Iniciando tomada de decisão...")
    try:
        # --- DEBUG: MOSTRAR AS ENTRADAS ---
        print("[DEBUG C3] Entradas recebidas:")
        print(f"  - Estágio Atual: {current_stage_id}")
        print(f"  - Query: {query[:100]}...")  # Mostra os primeiros 100 chars
        print(f"  - Rotas Possíveis: {possible_routes}")
        print(f"  - Histórico (Contexto): {conversation_history[:200]}...")  # Primeiros 200 chars

        # 1. Monta o prompt
        prompt = STAGE_DECISION_PROMPT

        # 2. Constrói a cadeia
        chain = prompt | llm.with_structured_output(StageTransitionDecision)

        # --- DEBUG: ANTES DA CHAMADA À IA ---
        print("[DEBUG C3] Preparado para invocar a cadeia LLM...")

        # 3. Invoca a cadeia (onde provavelmente está travando)
        decision = chain.invoke({
            "conversation_history": conversation_history,
            "current_stage_id": current_stage_id,
            "possible_routes": possible_routes,
            "query": query
        })

        # --- DEBUG: DEPOIS DA CHAMADA À IA ---
        print("[DEBUG C3] Cadeia LLM invocada com sucesso!")
        print(f"  - Próximo Estágio Decidido: {decision.proximo_stage_id}")
        print(f"  - Justificativa: {decision.justificativa}")

        print(f"✅ CÉREBRO 3: Decisão tomada. Próximo ID: {decision.proximo_stage_id}.")
        return decision.proximo_stage_id

    except Exception as e:
        # --- DEBUG: SE OCORRER UM ERRO ---
        print_error(f"[DEBUG C3] ERRO durante a decisão de estágio: {e}")
        import traceback
        traceback.print_exc()  # Imprime o traceback completo do erro

        print(f"❌ ERRO ao decidir o próximo estágio. Retornando estágio atual: {current_stage_id}.")
        return current_stage_id

def get_relevant_video_suggestion(ensemble_retriever: EnsembleRetriever, query: str) -> Optional[Dict[str, str]]:
    """
    Busca o documento mais relevante para a query e extrai o link do vídeo de seus metadados.
    """
    print("🎬 CÉREBRO 4: Buscando sugestão de vídeo...")
    try:
        # Usa o retriever híbrido, mas limita a busca a apenas 1 documento (k=1)
        context_docs = ensemble_retriever.invoke(query, k=1)

        if not context_docs:
            print("❌ CÉREBRO 4: Nenhum documento relevante encontrado para vídeo.")
            return None

        # O documento mais relevante é o primeiro da lista
        doc = context_docs[0]
        metadata = doc.metadata

        # O sistema de ingestão de dados deve salvar 'url_video' e 'titulo_video' nos metadados.
        video_url = metadata.get("url_video")
        video_title = metadata.get("titulo_video")

        # Se houver metadados de vídeo e o URL for de um vídeo (ex: YouTube), retorna a sugestão.
        if video_url and video_title and ("youtube.com" in video_url or "youtu.be" in video_url):
            print(f"✅ CÉREBRO 4: Vídeo sugerido: {video_title}")
            return {
                "title": video_title,
                "url": video_url
            }
        else:
            print("ℹ️ CÉREBRO 4: O documento mais relevante não possui metadados de vídeo ou não é um vídeo.")
            return None

    except Exception as e:
        print(f"❌ ERRO ao buscar sugestão de vídeo: {e}")
        return None


def get_dynamic_conversation_context(
        conversation_history: List[Dict[str, Any]],
        query: str,
        embedding_function
) -> str:
    """
    Usa uma BUSCA HÍBRIDA MANUAL com FUZZY MATCHING e limpeza de pontuação.
    """
    if not conversation_history: return "Nenhum histórico de conversa fornecido."
    print("🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Criando RAG em memória...")

    docs = [Document(page_content=msg["content"], metadata=msg) for msg in conversation_history if msg.get("content")]
    if not docs: return "Nenhum histórico de conversa encontrado."

    # --- LÓGICA DE BUSCA HÍBRIDA MANUAL APRIMORADA ---
    keyword_hits = []
    # CORREÇÃO: Removemos a pontuação da query antes de buscar
    query_words = {word.lower().strip('.,?!') for word in query.split()}
    similarity_threshold = 85

    for doc in docs:
        # CORREÇÃO: Removemos a pontuação de cada palavra do documento antes de comparar
        doc_words = [word.lower().strip('.,?!') for word in doc.page_content.split()]
        for q_word in query_words:
            if any(fuzz.ratio(q_word, d_word) > similarity_threshold for d_word in doc_words):
                keyword_hits.append(doc);
                break

    print(f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Encontradas {len(keyword_hits)} mensagens por palavra-chave aproximada.")

    # Busca Semântica (continua igual)
    db_temp = Chroma.from_documents(docs, embedding_function)
    vector_retriever = db_temp.as_retriever(search_kwargs={"k": 5})
    semantic_hits = vector_retriever.invoke(query)
    print(f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Encontradas {len(semantic_hits)} mensagens por similaridade semântica.")

    # Combinação e Limpeza (continua igual)
    combined_docs = keyword_hits + semantic_hits
    seen_content = set();
    unique_docs = []
    for doc in combined_docs:
        content_key = doc.page_content.strip()
        if content_key not in seen_content:
            seen_content.add(content_key);
            unique_docs.append(doc)
    print(f"🧠 CÉREBRO 2 (FUZZY HÍBRIDO v2): Contexto combinado com {len(unique_docs)} mensagens únicas.")

    if not unique_docs:
        print_warning("Nenhum documento relevante encontrado. Usando as 5 últimas mensagens como fallback.")
        unique_docs = docs[-5:]

    unique_docs.sort(key=lambda doc: float(doc.metadata.get('timestamp', 0)))

    formatted_context = "\n".join(
        [f"{doc.metadata.get('sender', 'desconhecido').capitalize()}: {doc.page_content}" for doc in unique_docs])

    print("\n[DEBUG C2] Contexto Final FUZZY HÍBRIDO v2 que será enviado para o Super Prompt:")
    print("-" * 20);
    print(formatted_context);
    print("-" * 20 + "\n")

    return formatted_context

# --- FUNÇÕES PRINCIPAIS ---

def load_models(chroma_client) -> tuple:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key: raise ValueError("ERRO: Chave GEMINI_API_KEY não configurada.")

    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=api_key, temperature=0.1)
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

    if not Path(CHROMA_PATH).exists(): raise FileNotFoundError(f"ERRO: DB Técnico não encontrado em {CHROMA_PATH}.")
    db_tecnico = Chroma(client=chroma_client, embedding_function=embeddings_model)

    print("INFO: Preparando retrievers para a Busca Híbrida...")
    # 1. Pega todos os documentos do nosso banco de dados técnico para a busca por palavra-chave.
    all_docs = db_tecnico.get(include=["metadatas", "documents"])
    docs_list = [Document(page_content=doc, metadata=meta) for doc, meta in
                 zip(all_docs['documents'], all_docs['metadatas'])]
    if not docs_list:
        raise FileNotFoundError(
            "ERRO CRÍTICO: O Banco de Dados Técnico (Chroma DB) está vazio. Por favor, execute o script de ingestão (ex: create_db.py) para popular o banco antes de iniciar o servidor."
        )

    # 2. Inicializa o retriever de palavra-chave (BM25) com esses documentos.
    keyword_retriever = BM25Retriever.from_documents(docs_list)
    keyword_retriever.k = 3  # Define que ele deve retornar os 3 melhores resultados.

    # 3. Cria o retriever vetorial a partir do nosso banco ChromaDB.
    vector_retriever = db_tecnico.as_retriever(search_kwargs={"k": 3})

    # 4. Inicializa o EnsembleRetriever, combinando os dois buscadores.
    # Damos pesos iguais para a busca vetorial e a de palavra-chave.
    ensemble_retriever = EnsembleRetriever(
        retrievers=[keyword_retriever, vector_retriever],
        weights=[0.5, 0.5]
    )
    print("✅ Retriever Híbrido (Ensemble) criado com sucesso.")

    if not Path(PLAYBOOK_PATH).exists(): raise FileNotFoundError(
        f"ERRO: Playbook de vendas não encontrado em {PLAYBOOK_PATH}.")

    with open(PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
        playbook = json.load(f)
    print("✅ LLM, Embedding, DB Técnico e Playbook carregados com sucesso.")
    return llm, ensemble_retriever, embeddings_model, playbook


# Em cerebro_ia.py, SUBSTITUA a função generate_sales_suggestions por esta:

def generate_sales_suggestions(
        llm: ChatGoogleGenerativeAI, ensemble_retriever: EnsembleRetriever,
        embeddings_model: GoogleGenerativeAIEmbeddings,
        playbook: Dict[str, Any], query: str, conversation_id: str, current_stage_id: str,
        full_conversation_history: List[Dict[str, Any]],
        client_data: Dict[str, Any],
        is_private_query: bool
) -> Dict[str, Any]:
    print("\n--- INICIANDO FLUXO DE GERAÇÃO ESTRATÉGICO V5.1 (DEBUG CÉREBRO 3) ---")

    # ETAPA 1: Cérebro 2 (Histórico Híbrido)
    conversation_context = get_dynamic_conversation_context(full_conversation_history, query, embeddings_model)
    print(f"🧠 CÉREBRO 2: Contexto híbrido da conversa carregado.")

    if is_private_query:
        print("⚡️ ROTA RÁPIDA: Consulta privada do vendedor. Pulando Cérebro 3.")
        stage_name = "Consulta Interna"
        stage_goal = "Responder a uma pergunta do vendedor com base no histórico."
        final_next_stage_id = current_stage_id
    else:
        # ROTA COMPLETA: Análise de mensagem do cliente.
        print("🌐 ROTA COMPLETA: Análise de mensagem do cliente. Executando Cérebro 3.")
        if not current_stage_id: current_stage_id = playbook["initial_stage"]
        current_stage_info = playbook["stages"].get(current_stage_id, {})
        stage_name = current_stage_info.get("name", "Análise Inicial")
        stage_goal = current_stage_info.get("goal", "Responder à dúvida e avançar a conversa.")
        possible_routes = "\n".join([f"- stage_id: {stage['stage_id']}, condition: {stage['condition']}" for stage in
                                     current_stage_info.get("possible_next_stages",
                                                            [])]) or "Nenhuma rota de próximo estágio definida."

        # =====================================================================
        # DEBUG: Printando as entradas do Cérebro 3 antes da chamada
        # =====================================================================
        print("\n" + "=" * 20 + " DEBUG: ENTRADA PARA O CÉREBRO 3 " + "=" * 20)
        print(f"  - Estágio Atual (ID): {current_stage_id}")
        print(f"  - Pergunta Atual (Query): {query}")
        print(f"  - Rotas Possíveis:\n{possible_routes}")
        print(f"  - Histórico da Conversa (Contexto):\n{conversation_context}")
        print("=" * 67 + "\n")
        # =====================================================================

        try:
            final_next_stage_id = decide_next_stage(
                llm=llm, conversation_history=conversation_context, current_stage_id=current_stage_id,
                possible_routes=possible_routes, query=query
            )
        except Exception as e:
            print_error(f"FALHA NO CÉREBRO 3 (Decisão de Estágio): {e}. Mantendo o estágio atual como fallback.")
            final_next_stage_id = current_stage_id

    # O restante do fluxo continua...
    # ETAPA 3: Cérebro 1 (Técnico)
    context_docs = ensemble_retriever.invoke(query)
    technical_context = "\n\n".join(
        [doc.page_content for doc in context_docs]) or "Nenhum contexto técnico relevante encontrado."
    print(f"📚 CÉREBRO 1: Contexto técnico recuperado.")

    # ETAPA 4: Síntese e Chamada ao LLM
    prompt = ChatPromptTemplate.from_template(SUPER_PROMPT_TEMPLATE)
    chain = prompt | llm.with_structured_output(AIResponse)
    client_data_text = json.dumps(client_data, indent=2,
                                  ensure_ascii=False) if client_data else "Nenhum dado estruturado sobre o cliente foi coletado ainda."
    print("🚀 Montando Super Prompt e fazendo a chamada única ao LLM...")
    ai_response = chain.invoke({
        "client_data": client_data_text, "conversation_history": conversation_context,
        "stage_name": stage_name, "stage_goal": stage_goal,
        "technical_context": technical_context, "query": query
    })
    print(f"✅ LLM retornou uma resposta estruturada.")

    # ETAPAS FINAIS (Vídeo e Formatação do Payload) continuam iguais...
    video_suggestion = get_relevant_video_suggestion(ensemble_retriever, query)
    suggestion_payload = {"immediate_answer": ai_response.sugestao_resposta, "follow_up_options": []}
    if ai_response.proximo_passo:
        suggestion_payload["follow_up_options"].append({"text": ai_response.proximo_passo, "is_recommended": True})
    if video_suggestion:
        suggestion_payload["video"] = video_suggestion

    return {"status": "success", "new_stage_id": final_next_stage_id, "suggestions": suggestion_payload}