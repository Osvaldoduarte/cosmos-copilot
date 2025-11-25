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
    DOCSTRING (Google Style): Limpa um dicionário de metadados para compatibilidade com ChromaDB.
    Converte listas em strings separadas por vírgula.
    """
    if not metadata:
        return {}

    clean_meta = {}
    for key, value in metadata.items():
        if isinstance(value, list):
            # A MÁGICA ACONTECE AQUI: Converte ['tag1', 'tag2'] em "tag1, tag2"
            clean_meta[key] = ", ".join([str(v) for v in value])
        elif value is None:
            clean_meta[key] = ""
        else:
            clean_meta[key] = value

    return clean_meta


def load_documents_from_jsonl() -> List[Document]:
    """Lê todos os arquivos refinado_*.jsonl da pasta data/"""
    documents = []
    # Busca arquivos usando pathlib
    files = list(DATA_DIR_PATH.glob("refinado_*.jsonl"))

    print(f"📂 Buscando arquivos em: {DATA_DIR_PATH}")
    print(f"📄 Arquivos encontrados: {len(files)}")

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_number, line in enumerate(f):
                    line = line.strip()
                    if not line: continue

                    try:
                        data = json.loads(line)

                        # Pega o conteúdo e os metadados brutos
                        content = data.get("content", "")
                        raw_metadata = data.get("metadata", {})

                        # IMPORTANTE: Limpa os metadados antes de criar o Documento
                        clean_metadata = _clean_metadata(raw_metadata)

                        doc = Document(
                            page_content=content,
                            metadata=clean_metadata
                        )
                        documents.append(doc)
                    except json.JSONDecodeError:
                        print(f"⚠️ Erro de JSON na linha {line_number} do arquivo {file_path.name}")
        except Exception as e:
            print(f"❌ Erro ao ler arquivo {file_path.name}: {e}")

    print(f"📚 Total de trechos (chunks) carregados: {len(documents)}")
    return documents


def create_database():
    """Função Principal: Recria o Banco de Dados"""

    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ ERRO: GOOGLE_API_KEY não encontrada no .env")
        return

    print("🧠 Inicializando modelo de Embeddings (models/embedding-001)...")
    embeddings_model = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key
    )

    docs = load_documents_from_jsonl()
    if not docs:
        print("❌ Nenhum documento encontrado. Verifique a pasta 'data/'.")
        return

    # --- Lógica de Seleção de Banco (Remoto vs Local) ---
    if CHROMA_HOST:
        print(f"🌐 Conectando ao ChromaDB Remoto em: {CHROMA_HOST}...")
        try:
            # Lógica robusta de parsing de URL
            from urllib.parse import urlparse

            url_str = CHROMA_HOST
            if not url_str.startswith(('http://', 'https://')):
                url_str = f"http://{url_str}"  # Assume http por padrão se não informado

            parsed = urlparse(url_str)
            host = parsed.hostname
            port = parsed.port or 8000
            ssl_enabled = parsed.scheme == 'https'

            if not host:  # Fallback
                host = CHROMA_HOST.split(":")[0]

            print(f"   -> Host: {host}, Port: {port}, SSL: {ssl_enabled}")

            client = chromadb.HttpClient(host=host, port=port, ssl=ssl_enabled)

            # Tenta limpar a coleção antiga
            try:
                client.delete_collection(COLLECTION_NAME)
                print(f"🗑️ Coleção remota '{COLLECTION_NAME}' apagada.")
            except:
                pass

            # Inserção em Lote (Batch) para performance
            print("🚀 Inserindo documentos no banco remoto...")
            Chroma.from_documents(
                client=client,
                documents=docs,
                embedding=embeddings_model,
                collection_name=COLLECTION_NAME
            )
            print("✅ Banco Remoto populado com sucesso!")

        except Exception as e:
            print(f"❌ Erro ao conectar no Chroma Remoto: {e}")
            traceback.print_exc()

    else:
        # --- MODO LOCAL ---
        print(f"🏠 Configurando ChromaDB Local em: {CHROMA_PATH_LOCAL}")

        if os.path.exists(CHROMA_PATH_LOCAL):
            print("🧹 Removendo banco de dados antigo...")
            shutil.rmtree(CHROMA_PATH_LOCAL)

        print("🚀 Inserindo documentos e gerando vetores (isso pode demorar um pouco)...")
        try:
            vector_db = Chroma.from_documents(
                documents=docs,
                embedding=embeddings_model,
                persist_directory=CHROMA_PATH_LOCAL,
                collection_name=COLLECTION_NAME
            )
            # Nas versões recentes do Langchain/Chroma, o persist é automático,
            # mas manter a chamada não faz mal.
            vector_db.persist()
            print("✅ Banco de Dados Local recriado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao criar banco local: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    create_database()