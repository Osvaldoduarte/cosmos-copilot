import os
import json
import chromadb
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.pydantic_v1 import BaseModel, Field


# --- CONFIGURAÇÕES GLOBAIS ---
CORE_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = CORE_DIR.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
CHROMA_PATH = str(BACKEND_DIR / "chroma_db_local")
CHROMA_CONVERSAS_PATH = str(BACKEND_DIR / "chroma_db_conversas")
PLAYBOOK_PATH = str(DATA_DIR / "playbook_vendas.json")
GEMINI_MODEL_NAME = "gemini-2.5-flash"

# Carrega as variáveis de ambiente (do arquivo .env.local)
load_dotenv()

# --- NOVA LÓGICA DE CONEXÃO AO CHROMA DB ---
CHROMA_HOST = os.environ.get("CHROMA_HOST")
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    raise ValueError("A variável de ambiente GEMINI_API_KEY não foi definida.")

# Inicializa o modelo de embeddings que será usado em ambos os casos
embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

if CHROMA_HOST:
    print("✅ Conectando ao banco de dados ChromaDB remoto no Cloud Run...")
    # Se a variável CHROMA_HOST existe, conecta-se ao servidor na nuvem
    # O port 443 e ssl=True são para conexões HTTPS seguras
    chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=443, ssl=True)
else:
    print("ℹ️  Usando banco de dados ChromaDB local. (Para deploy, configure CHROMA_HOST)")
    # Se não, continua usando o banco de dados da pasta local
    CHROMA_PATH = str(Path(__file__).parent.parent / "chroma_db_local")
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)

# --- DEFINIÇÃO DA ESTRUTURA DE SAÍDA ---
class AIResponse(BaseModel):
    sugestao_resposta: str = Field(
        description="A resposta direta e factual para a pergunta técnica do cliente, baseada no CONTEXTO TÉCNICO.")
    proximo_passo: Optional[str] = Field(
        description="Uma pergunta ou sugestão de próximo passo para o vendedor enviar ao cliente, alinhada com o OBJETIVO ESTRATÉGICO.")
    proximo_stage_id: str = Field(description="O ID do próximo estágio para o qual a conversa deve avançar, escolhido a partir das opções fornecidas.")


# --- TEMPLATE DO NOVO SUPER PROMPT ---
SUPER_PROMPT_TEMPLATE = """
Você é o "Cosmos Copilot", um assistente de vendas especialista em IA para o sistema CosmosERP.

Sua missão é analisar o contexto completo de uma interação com o cliente e gerar uma resposta estruturada em JSON contendo três partes: uma resposta técnica para a dúvida atual, uma sugestão estratégica de próximo passo, e o ID do próximo estágio da conversa.

---
CONTEXTO GERAL (CÉREBRO 2 - O CLIENTE E A CONVERSA)
Este é o histórico completo da conversa até agora. Use-o para entender quem é o cliente, o que já foi dito e o tom da conversa.
{conversation_history}
---
OBJETIVO ESTRATÉGICO (CÉREBRO 3 - O PLAYBOOK DE VENDAS)
Com base na conversa, o estágio atual da venda é '{stage_name}'. O seu objetivo agora é: '{stage_goal}'.

ROTAS POSSÍVEIS PARA O PRÓXIMO ESTÁGIO:
Abaixo está uma lista de próximos estágios possíveis e as condições para ir para cada um. Analise o histórico e a pergunta atual para escolher o ID do estágio mais apropriado.
{possible_routes}
---
EVIDÊNCIAS TÉCNICAS (CÉREBRO 1 - A BASE DE CONHECIMENTO)
Para responder à pergunta do cliente, utilize estritamente as seguintes informações técnicas sobre o produto. Não invente funcionalidades.
{technical_context}
---

PERGUNTA ATUAL DO CLIENTE: "{query}"

Baseado em TODOS os contextos acima, gere a sua resposta.
- Se a pergunta for claramente uma consulta interna do vendedor para tirar uma dúvida, foque em fornecer a 'sugestao_resposta' e retorne o 'proximo_passo' como nulo. # <-- MUDANÇA AQUI
- Se a pergunta for do cliente, forneça tanto a 'sugestao_resposta' quanto o 'proximo_passo'.
- Você DEVE escolher o 'proximo_stage_id' mais lógico a partir da lista de 'ROTAS POSSÍVEIS'.
"""

# --- PROMPTS AUXILIARES ---
TRIAGE_PROMPT_TEMPLATE = """
Analise a mensagem do usuário e classifique-a em uma das seguintes categorias: 'saudacao_inicial', 'resposta_qualificacao', 'pergunta_tecnica', 'escolha_de_opcao', 'pergunta_conversacional', 'comentario_geral'.
Responda APENAS com uma única string da categoria.
Mensagem do usuário: "{query}"
Categoria:
"""
TRIAGE_PROMPT = ChatPromptTemplate.from_template(TRIAGE_PROMPT_TEMPLATE)


# --- FUNÇÕES AUXILIARES ---

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
    try:
        chain = prompt_template | llm | StrOutputParser()
        intent = chain.invoke({"query": query})
        return intent.strip().lower().replace("'", "").replace('"', '')
    except Exception as e:
        print(f"❌ ERRO ao classificar intenção: {e}")
        return "geral"


# Renomeie e substitua a função antiga get_full_conversation_history por esta
def get_hybrid_context_history(conversation_id: str, query: str, embeddings_model, k: int = 10) -> str:
    """
    Busca um contexto híbrido: as 'k' mensagens mais recentes + as 'k' mais relevantes para a query.
    Isso otimiza o número de tokens enviados para o LLM.
    """
    try:
        db = get_or_create_conversation_db(conversation_id, embeddings_model)

        # --- PARTE 1: BUSCAR MENSAGENS RELEVANTES (RAG) ---
        # Busca no banco por mensagens semanticamente similares à pergunta atual.
        relevant_docs = db.similarity_search(query, k=k)
        print(f"🧠 CÉREBRO 2: Encontradas {len(relevant_docs)} mensagens relevantes.")

        # --- PARTE 2: BUSCAR MENSAGENS RECENTES (CRONOLÓGICO) ---
        # Pega todas as mensagens para encontrar as mais recentes.
        all_results = db.get(include=["metadatas", "documents"])
        if not all_results or not all_results.get('ids'):
            recent_docs = []
        else:
            # Monta a lista completa de mensagens.
            all_messages = [{**meta, 'content': doc} for meta, doc in
                            zip(all_results['metadatas'], all_results['documents'])]
            # Ordena pela data/hora para garantir a ordem cronológica.
            all_messages.sort(
                key=lambda x: float(x['timestamp']) if x.get('timestamp') and x['timestamp'] != 'None' else 0,
                reverse=True)
            # Pega as 'k' mensagens mais recentes (as primeiras da lista invertida).
            recent_docs_as_dict = all_messages[:k]
            # Converte de volta para o formato de Documento do LangChain.
            recent_docs = [Document(page_content=msg['content'], metadata=msg) for msg in recent_docs_as_dict]

        print(f"🧠 CÉREBRO 2: Encontradas {len(recent_docs)} mensagens recentes.")

        # --- PARTE 3: COMBINAR E FORMATAR ---
        # Combina as duas listas de documentos.
        combined_docs = relevant_docs + recent_docs

        # Remove duplicatas, mantendo a relevância e a recentude.
        # Usamos o conteúdo da mensagem como chave para identificar duplicatas.
        unique_docs_map = {doc.page_content: doc for doc in combined_docs}
        unique_docs = list(unique_docs_map.values())

        # Ordena a lista final e única pela data/hora para apresentar ao LLM de forma cronológica.
        unique_docs.sort(
            key=lambda doc: float(doc.metadata['timestamp']) if doc.metadata.get('timestamp') and doc.metadata[
                'timestamp'] != 'None' else 0)

        # Formata o histórico final em uma string legível.
        formatted_history = "\n".join(
            [f"{doc.metadata.get('sender', 'desconhecido').capitalize()}: {doc.page_content}" for doc in unique_docs]
        )

        return formatted_history if formatted_history else "Nenhum histórico de conversa encontrado."

    except Exception as e:
        print(f"❌ ERRO ao buscar o histórico híbrido da conversa: {e}")
        return "Não foi possível recuperar o histórico da conversa."

# --- FUNÇÕES PRINCIPAIS ---

def load_models() -> tuple:
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key: raise ValueError("ERRO: Chave GEMINI_API_KEY não configurada.")
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=api_key, temperature=0.1)
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    if not Path(CHROMA_PATH).exists(): raise FileNotFoundError(f"ERRO: DB Técnico não encontrado em {CHROMA_PATH}.")
    db_tecnico = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings_model)
    if not Path(PLAYBOOK_PATH).exists(): raise FileNotFoundError(
        f"ERRO: Playbook de vendas não encontrado em {PLAYBOOK_PATH}.")
    with open(PLAYBOOK_PATH, 'r', encoding='utf-8') as f:
        playbook = json.load(f)
    print("✅ LLM, Embedding, DB Técnico e Playbook carregados com sucesso.")
    return llm, db_tecnico, embeddings_model, playbook


# Substitua sua função generate_sales_suggestions inteira por esta.
def generate_sales_suggestions(
        llm: ChatGoogleGenerativeAI, db_tecnico: Chroma, embeddings_model: GoogleGenerativeAIEmbeddings,
        playbook: Dict[str, Any], query: str, conversation_id: str, current_stage_id: str
) -> Dict[str, Any]:
    print("\n--- INICIANDO FLUXO DE GERAÇÃO ESTRATÉGICO V2.2 ---")

    # --- ETAPA 1: COLETAR CONTEXTO DO CÉREBRO 2 (HISTÓRICO) ---
    # Usamos nossa função para obter o histórico completo e cronológico da conversa.
    conversation_history = get_hybrid_context_history(conversation_id, query, embeddings_model)
    print(f"🧠 CÉREBRO 2: Histórico da conversa carregado.")

    # --- ETAPA 2: DEFINIR ESTRATÉGIA COM CÉREBRO 3 (PLAYBOOK) ---
    # Classificamos a intenção da mensagem mais recente do cliente.
    triage_intent = get_intent_from_query(llm, query, TRIAGE_PROMPT)

    # Se não houver estágio atual, começamos pelo inicial definido no playbook.
    if not current_stage_id:
        current_stage_id = playbook["initial_stage"]

    # Buscamos as informações do estágio atual no playbook.
    current_stage_info = playbook["stages"].get(current_stage_id, {})
    stage_name = current_stage_info.get("name", "Análise Inicial")

    # Lógica dinâmica para definir o objetivo com base na intenção do cliente.
    if triage_intent == "pergunta_tecnica":
        stage_goal = current_stage_info.get("goal", "Responder a uma dúvida técnica específica sobre o produto.")
    elif triage_intent == "resposta_qualificacao":
        stage_goal = "Processar as informações fornecidas pelo cliente e confirmar o entendimento."
    else:
        stage_goal = "Manter a conversa fluindo e guiar para o próximo passo lógico."

    # --- NOVO: Extrair e formatar as rotas possíveis para o LLM ---
    # Buscamos a lista de próximos estágios possíveis a partir do estágio atual.
    possible_next_stages = current_stage_info.get("possible_next_stages", [])

    # Formatamos essa lista em uma string legível para ser injetada no prompt.
    # Ex: "stage_id: stage_qualification, condition: A mensagem do cliente é uma saudação..."
    possible_routes = "\n".join(
        [f"- stage_id: {stage['stage_id']}, condition: {stage['condition']}" for stage in possible_next_stages]
    )
    if not possible_routes:
        possible_routes = "Nenhuma rota de próximo estágio definida. Mantenha o estágio atual."

    print(f"🎯 CÉREBRO 3: Estratégia definida. Estágio: '{stage_name}'. Rotas: {len(possible_next_stages)} opções.")

    # --- ETAPA 3: COLETAR EVIDÊNCIAS DO CÉREBRO 1 (TÉCNICO) ---
    # Buscamos na base de conhecimento técnica por informações relevantes para a pergunta do cliente.
    context_docs = db_tecnico.similarity_search(query, k=3)
    technical_context = "\n\n".join([doc.page_content for doc in context_docs])
    if not technical_context:
        technical_context = "Nenhuma informação técnica encontrada sobre este assunto."
    print(f"📚 CÉREBRO 1: Contexto técnico recuperado.")

    # --- ETAPA 4: SÍNTESE E CHAMADA ÚNICA AO LLM COM O "SUPER PROMPT" ---
    # Criamos o prompt a partir do nosso template atualizado.
    prompt = ChatPromptTemplate.from_template(SUPER_PROMPT_TEMPLATE)

    # Construímos a cadeia (chain) LangChain, forçando a saída para o nosso modelo AIResponse.
    chain = prompt | llm.with_structured_output(AIResponse)

    print("🚀 Montando Super Prompt e fazendo a chamada única ao LLM...")
    # Invocamos a cadeia com todos os contextos que coletamos, incluindo as novas 'rotas'.
    ai_response = chain.invoke({
        "conversation_history": conversation_history,
        "stage_name": stage_name,
        "stage_goal": stage_goal,
        "possible_routes": possible_routes,  # <-- Injetando as rotas no prompt
        "technical_context": technical_context,
        "query": query
    })

    print(f"✅ LLM retornou uma resposta estruturada. Próximo estágio decidido: '{ai_response.proximo_stage_id}'")

    # --- ETAPA 5: FORMATAR PAYLOAD PARA O FRONTEND ---
    # Mapeamos a resposta estruturada da IA para o formato que o frontend espera.
    suggestion_payload = {
        "immediate_answer": ai_response.sugestao_resposta,
        "text_options": [],
        "follow_up_options": [
            {
                "tone": "amigavel",
                "text": ai_response.proximo_passo,
                "is_recommended": True
            }
        ],
        "video": None
    }

    # AQUI ESTÁ A MUDANÇA FINAL: O novo ID de estágio agora vem da decisão da IA.
    return {"status": "success", "new_stage_id": ai_response.proximo_stage_id, "suggestions": suggestion_payload}