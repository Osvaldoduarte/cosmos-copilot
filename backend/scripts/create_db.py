# Em backend/scripts/create_db.py
import os
import shutil
import json
import traceback
from dotenv import load_dotenv
from typing import List, Dict, Any
from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pathlib import Path
from urllib.parse import urlparse
import chromadb
from langchain_community.vectorstores.utils import filter_complex_metadata

# --- 💡 CARREGAMENTO DE VARIÁVEIS DE AMBIENTE ---
try:
    BACKEND_DIR_PATH = Path(__file__).parent.parent.resolve()
    env_path = BACKEND_DIR_PATH / ".env"

    if not env_path.exists():
        print(f"⚠️  Atenção [create_db]: Arquivo .env não encontrado em {env_path}")
    else:
        load_dotenv(dotenv_path=env_path)
        print(f"✅ [create_db] Variáveis de ambiente carregadas.")
except Exception as e:
    print(f"❌ Erro ao carregar .env: {e}")

# --- CONFIGURAÇÃO DE CAMINHOS ---
CHROMA_PATH_LOCAL = str(BACKEND_DIR_PATH / "chroma_db_local")
DATA_DIR_PATH = BACKEND_DIR_PATH / "data"
CHROMA_HOST = os.environ.get("CHROMA_HOST")
COLLECTION_NAME = "evolution"

def _clean_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    DOCSTRING (Google Style): Limpa um dicionário de metadados,
    removendo valores que não são escalares (listas, dicts aninhados)
    que o ChromaDB rejeita.

    Args:
        metadata: Dicionário de metadados potencialmente complexos.

    Returns:
        Dicionário de metadados limpos, contendo apenas valores compatíveis com o ChromaDB.
    """
    cleaned_metadata = {}
    for key, value in metadata.items():
        # ChromaDB só aceita str, int, float, bool, ou None.
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned_metadata[key] = value
        # Qualquer outro tipo (list, dict, object) é ignorado.
    return cleaned_metadata

# --- FUNÇÃO DE LEITURA DOS JSONL ---
def load_data_from_jsonl() -> List[Document]:
    print("\nINFO: Processando arquivos de dados refinados (refinado_*.jsonl)...")
    all_chunks = []
    refined_files = list(DATA_DIR_PATH.glob("refinado_*.jsonl"))

    if not refined_files:
        print("    -> Nenhum arquivo .jsonl refinado encontrado em /data.")
        return []

    for file_path in refined_files:
        with file_path.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            print(f"AVISO: Arquivo refinado {file_path.name} está vazio.")
            continue

        # Tenta ler o primeiro registro como cabeçalho (metadados simples)
        try:
            first_line = json.loads(lines[0])
        except json.JSONDecodeError:
            first_line = {}

        # Percorre o restante das linhas (pode ser formato antigo ou novo)
        for line in lines[1:]:
            try:
                data = json.loads(line)

                # --- Novo formato (chunks com content/metadata) ---
                if "content" in data:
                    combined_content = data["content"]
                    metadata = data.get("metadata", {})
                    metadata.update({
                        "source": data.get("source_document_id", file_path.name),
                        "titulo": data.get("title", "")
                    })
                    all_chunks.append(Document(page_content=combined_content, metadata=metadata))
                    continue

                # --- Formato antigo (pergunta/resposta) ---
                question = data.get("pergunta")
                answer = data.get("resposta")
                if not question or not answer:
                    continue

                combined_content = f"Pergunta: {question}\nResposta: {answer}"
                metadata = {
                    'source': first_line.get("source_file", file_path.name),
                    'type': first_line.get("source_type", "desconhecido"),
                    **({'url_video': first_line.get("video_url")} if first_line.get("video_url") else {})
                }
                all_chunks.append(Document(page_content=combined_content, metadata=metadata))

            except json.JSONDecodeError:
                print(f"AVISO: Linha JSON mal formatada em {file_path.name} ignorada: {line[:50]}...")

    print(f"    -> {len(all_chunks)} chunks totais extraídos de {len(refined_files)} arquivos .jsonl.")
    return all_chunks


# --- FUNÇÃO PRINCIPAL ---
def create_database():
    # Atualizei a versão para rastreamento
    print("\n--- [FINAL] CRIANDO O BANCO DE DADOS VETORIAL (v1.2.7 - Limpeza de Tipo e Metadados Manual) ---")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ ERRO: GEMINI_API_KEY não configurada.")
        return

    all_chunks = load_data_from_jsonl()

    if not all_chunks:
        print("\nAVISO: Nenhum chunk de dados (.jsonl) encontrado para processar.")
        return

    # ✅ REFATORAÇÃO DE FILTRAGEM: O coração da correção.
    filtered_chunks = []
    total_chunks = len(all_chunks)

    for i, chunk in enumerate(all_chunks):
        # 1. Checagem de Tipo (Programação Defensiva)
        if not isinstance(chunk, Document):
            # Esta linha captura as strings que escapam da validação, prevenindo o AttributeError.
            print(f"⚠️ AVISO: Chunk {i + 1}/{total_chunks} é do tipo inesperado ({type(chunk).__name__}). Pulando.")
            continue

        # 2. Limpeza Manual de Metadados (Resolve o ValueError do ChromaDB)
        try:
            chunk.metadata = _clean_metadata(chunk.metadata)
            filtered_chunks.append(chunk)
        except Exception as e:
            # Caso ocorra algum erro inesperado na limpeza do dict de metadados.
            print(f"❌ ERRO Inesperado ao limpar metadados do Chunk {i + 1}/{total_chunks}: {e}. Pulando.")

    all_chunks = filtered_chunks  # Renomeia a lista limpa

    print(f"\nINFO: Total de {len(all_chunks)} chunks para serem adicionados ao DB.")
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

    if CHROMA_HOST:
        print(f"INFO: Conectando ao ChromaDB REMOTO em: {CHROMA_HOST}")
        try:
            url_to_parse = CHROMA_HOST
            if not url_to_parse.startswith(('http://', 'https://')):
                url_to_parse = 'https://' + url_to_parse

            parsed_url = urlparse(url_to_parse)
            host = parsed_url.netloc.split(':')[0] if parsed_url.netloc else parsed_url.path.split(':')[0]
            ssl_enabled = parsed_url.scheme == 'https'
            port = parsed_url.port or (443 if ssl_enabled else 80)

            client = chromadb.HttpClient(host=host, port=port, ssl=ssl_enabled)
            client.heartbeat()

            try:
                client.delete_collection(name=COLLECTION_NAME)
            except Exception:
                print(f"INFO: Coleção '{COLLECTION_NAME}' não existia. Criando uma nova.")

            db = Chroma.from_documents(all_chunks, embeddings_model, collection_name=COLLECTION_NAME, client=client)
            count = db._collection.count()
            print(f"✅ DB Vetorial REMOTO '{COLLECTION_NAME}' criado/atualizado com {count} chunks.")

        except Exception as e:
            print(f"❌ ERRO ao conectar ou popular o DB remoto: {e}")
            traceback.print_exc()
    else:
        if os.path.exists(CHROMA_PATH_LOCAL):
            print(f"INFO: Apagando banco de dados LOCAL antigo em '{CHROMA_PATH_LOCAL}'...")
            shutil.rmtree(CHROMA_PATH_LOCAL)
        print(f"INFO: Criando novo DB vetorial LOCAL em: {CHROMA_PATH_LOCAL}...")

        db = Chroma.from_documents(all_chunks, embeddings_model, persist_directory=CHROMA_PATH_LOCAL, collection_name=COLLECTION_NAME)
        db.persist()
        count = db._collection.count()
        print(f"✅ DB Vetorial LOCAL '{COLLECTION_NAME}' criado com {count} chunks.")


if __name__ == "__main__":
    create_database()
