import os
import json
import chromadb
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate
from langchain.retrievers import BM25Retriever, EnsembleRetriever
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
class StageTransitionDecision(BaseModel):
    proximo_stage_id: str = Field(description="O ID do próximo estágio mais lógico para o qual a conversa deve avançar, escolhido estritamente a partir da lista de 'ROTAS POSSÍVEIS'.")
    justificativa: str = Field(description="Uma breve justificativa da sua escolha, referenciando o histórico da conversa.")

class AIResponse(BaseModel):
    sugestao_resposta: str = Field(
        description="A resposta direta e factual para a pergunta técnica do cliente, baseada no CONTEXTO TÉCNICO.")
    proximo_passo: Optional[str] = Field(
        description="Uma pergunta ou sugestão de próximo passo para o vendedor enviar ao cliente, alinhada com o OBJETIVO ESTRATÉGICO.")


# --- TEMPLATE DO NOVO SUPER PROMPT ---
SUPER_PROMPT_TEMPLATE = """
Você é o "Cosmos Copilot", um assistente de vendas especialista em IA para o sistema CosmosERP.

Sua missão é analisar o contexto completo de uma interação com o cliente e gerar uma resposta estruturada em JSON contendo duas partes: uma resposta técnica para a dúvida atual, e uma sugestão estratégica de próximo passo. O ID do próximo estágio é decidido externamente.

---
CONTEXTO GERAL (CÉREBRO 2 - O CLIENTE E A CONVERSA)
Este é o histórico completo da conversa até agora. Use-o para entender quem é o cliente, o que já foi dito e o tom da conversa.
{conversation_history}
---
OBJETIVO ESTRATÉGICO (CÉREBRO 3 - O PLAYBOOK DE VENDAS)
Com base na conversa, o estágio atual da venda é '{stage_name}'. O seu objetivo agora é: '{stage_goal}'.

EVIDÊNCIAS TÉCNICAS (CÉREBRO 1 - A BASE DE CONHECIMENTO)
Para responder à pergunta do cliente, utilize estritamente as seguintes informações técnicas sobre o produto. Não invente funcionalidades.
{technical_context}
---

PERGUNTA ATUAL DO CLIENTE: "{query}"

Baseado em TODOS os contextos acima, gere a sua resposta.
- Se a pergunta for claramente uma consulta interna do vendedor para tirar uma dúvida, foque em fornecer a 'sugestao_resposta' e retorne o 'proximo_passo' como nulo.
- Se a pergunta for do cliente, forneça tanto a 'sugestao_resposta' quanto o 'proximo_passo'.
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


def decide_next_stage(llm: ChatGoogleGenerativeAI,conversation_history: str,current_stage_id: str,possible_routes: str,query: str) -> str:
    """
    Função dedicada a usar o LLM para determinar o próximo estágio de vendas.
    Retorna o ID do próximo estágio ou o estágio atual em caso de falha.
    """
    print(f"🔄 CÉREBRO 3: Iniciando tomada de decisão de estágio...")
    try:
        # 1. Monta o prompt específico para a decisão.
        prompt = STAGE_DECISION_PROMPT

        # 2. Constrói a cadeia, forçando a saída para o StageTransitionDecision.
        # Usa o with_structured_output com o modelo de decisão
        chain = prompt | llm.with_structured_output(StageTransitionDecision)

        # 3. Invoca a cadeia.
        decision = chain.invoke({
            "conversation_history": conversation_history,
            "current_stage_id": current_stage_id,
            "possible_routes": possible_routes,
            "query": query
        })

        print(f"✅ CÉREBRO 3: Decisão tomada. Próximo ID: {decision.proximo_stage_id}. Justificativa: {decision.justificativa[:50]}...")
        # Retorna o ID do próximo estágio.
        return decision.proximo_stage_id

    except Exception as e:
        print(f"❌ ERRO ao decidir o próximo estágio. Retornando estágio atual: {current_stage_id}. ERRO: {e}")
        # Em caso de falha, retorna o estágio atual para segurança.
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
        # 1. Combina as duas listas de documentos.
        combined_docs = relevant_docs + recent_docs

        # 2. Remove duplicatas, usando o conteúdo da mensagem como chave.
        seen_content = set()
        unique_docs = []
        for doc in combined_docs:
            # A normalização (strip) ajuda na identificação de conteúdos idênticos.
            content_key = doc.page_content.strip()
            # Adiciona apenas se for a primeira vez que esse conteúdo é visto
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_docs.append(doc)

        print(f"🧠 CÉREBRO 2: Contexto final com {len(unique_docs)} mensagens únicas.")

        # 3. Ordena a lista final pela data/hora (timestamp), do mais antigo para o mais novo (Cronológico).
        unique_docs.sort(
            key=lambda doc: float(doc.metadata['timestamp']) if doc.metadata.get('timestamp') and doc.metadata[
                'timestamp'] != 'None' else 0,
            reverse=False  # Garante ordem crescente por tempo (mais antigo primeiro)
        )

        # 4. Formata o histórico final em uma string legível.
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

def generate_sales_suggestions(
        llm: ChatGoogleGenerativeAI, ensemble_retriever: EnsembleRetriever, embeddings_model: GoogleGenerativeAIEmbeddings,
        playbook: Dict[str, Any], query: str, conversation_id: str, current_stage_id: str
) -> Dict[str, Any]:
    print("\n--- INICIANDO FLUXO DE GERAÇÃO ESTRATÉGICO V2.2 ---")

    # --- ETAPA 1: COLETAR CONTEXTO DO CÉREBRO 2 (HISTÓRICO) ---
    # Usamos nossa função para obter o histórico completo e cronológico da conversa.
    conversation_history = get_hybrid_context_history(conversation_id, query, embeddings_model)
    print(f"🧠 CÉREBRO 2: Histórico da conversa carregado.")

    # --- ETAPA 2: DEFINIR ESTRATÉGIA COM CÉREBRO 3 (PLAYBOOK) ---
    triage_intent = get_intent_from_query(llm, query, TRIAGE_PROMPT)

    if not current_stage_id:
        current_stage_id = playbook["initial_stage"]

    current_stage_info = playbook["stages"].get(current_stage_id, {})
    stage_name = current_stage_info.get("name", "Análise Inicial")

    if triage_intent == "pergunta_tecnica":
        stage_goal = current_stage_info.get("goal", "Responder a uma dúvida técnica específica sobre o produto.")
    elif triage_intent == "resposta_qualificacao":
        stage_goal = "Processar as informações fornecidas pelo cliente e confirmar o entendimento."
    else:
        stage_goal = "Manter a conversa fluindo e guiar para o próximo passo lógico."

    # --- NOVO: Extrair e formatar as rotas possíveis para a DECISÃO DE ESTÁGIO ---
    possible_next_stages = current_stage_info.get("possible_next_stages", [])

    # Formatamos essa lista em uma string legível para ser usada na função decide_next_stage.
    possible_routes = "\n".join(
        [f"- stage_id: {stage['stage_id']}, condition: {stage['condition']}" for stage in possible_next_stages]
    )
    if not possible_routes:
        possible_routes = "Nenhuma rota de próximo estágio definida. Mantenha o estágio atual."

    # --- NOVO: Tomada de decisão de estágio (Cadeia Separada) ---
    final_next_stage_id = decide_next_stage(
        llm=llm,
        conversation_history=conversation_history,
        current_stage_id=current_stage_id,
        possible_routes=possible_routes,
        query=query
    )

    # --- ETAPA 3: COLETAR EVIDÊNCIAS DO CÉREBRO 1 (TÉCNICO) ---
    # Buscamos na base de conhecimento técnica por informações relevantes para a pergunta do cliente.
    context_docs = ensemble_retriever.invoke(query)
    technical_context = "\n\n".join([doc.page_content for doc in context_docs])
    if not technical_context:
        technical_context = "Nenhum contexto técnico relevante encontrado."
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
        "technical_context": technical_context,
        "query": query
    })

    print(f"✅ LLM retornou uma resposta estruturada. Próximo estágio decidido: '{ai_response.proximo_stage_id}'")

    # --- NOVO: ETAPA 5 (CÉREBRO 4) - BUSCAR SUGESTÃO DE VÍDEO ---
    # Chamamos a nova função que busca o vídeo mais relevante.
    video_suggestion = get_relevant_video_suggestion(ensemble_retriever, query)

    # --- ETAPA 6 (Antiga ETAPA 5) - FORMATAR PAYLOAD PARA O FRONTEND ---
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
        "video": video_suggestion  # <--- INCLUSÃO DO OBJETO DE SUGESTÃO DE VÍDEO
    }

    # O novo ID de estágio agora vem da decisão externa.
    return {"status": "success", "new_stage_id": final_next_stage_id, "suggestions": suggestion_payload}
