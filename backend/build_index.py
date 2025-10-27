# build_index.py
import pickle
import os
from pathlib import Path
from dotenv import load_dotenv

import chromadb
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain.docstore.document import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from core import cerebro_ia # Reutiliza sua função de inicialização

# Carrega variáveis de ambiente (CHROMA_HOST, GEMINI_API_KEY, etc)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

CHROMA_PATH = str(Path(__file__).parent / "chroma_db_local")
OUTPUT_FILE = "bm25_retriever.pkl"

def build_and_save_index():
    """
    Conecta ao ChromaDB, baixa todos os documentos,
    cria o BM25Retriever e o salva em um arquivo pickle.
    """
    print("INFO: Iniciando o processo de build do índice...")

    try:
        # 1. Inicializa o cliente Chroma
        print(f"INFO: Conectando ao ChromaDB em {os.getenv('CHROMA_HOST')}...")
        chroma_client = cerebro_ia.initialize_chroma_client()
        if not chroma_client:
            print("ERRO: Falha ao inicializar o cliente ChromaDB.")
            return

        api_key = os.getenv("GEMINI_API_KEY")
        embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

        COLLECTION_NAME = "evolution"  # O nome da coleção no servidor remoto
        print(f"INFO: Acessando a coleção remota '{COLLECTION_NAME}'...")

        # Inicialização correta para cliente remoto via LangChain Chroma:
        db_tecnico = Chroma(
            client=chroma_client,  # Usa o cliente remoto já conectado
            collection_name=COLLECTION_NAME,  # Especifica o nome da coleção remota
            embedding_function=embeddings_model
        )
        # --- FIM DA CORREÇÃO ---

        # 3. Baixa TODOS os documentos (Agora do servidor remoto, da coleção 'evolution')
        print("INFO: Baixando todos os documentos do ChromaDB remoto... (Isso pode demorar)")
        # A linha abaixo agora funcionará corretamente
        all_docs = db_tecnico.get(include=["metadatas", "documents"])

        # 3. Baixa TODOS os documentos (A parte LENTA)
        print("INFO: Baixando todos os documentos do ChromaDB... (Isso pode demorar)")
        all_docs = db_tecnico.get(include=["metadatas", "documents"])
        docs_list = [
            Document(page_content=doc, metadata=meta)
            for doc, meta in zip(all_docs['documents'], all_docs['metadatas'])
        ]
        print(f"INFO: {len(docs_list)} documentos baixados.")

        if not docs_list:
            print("ERRO: O Banco de Dados Técnico (Chroma DB) está vazio.")
            return

        # 4. Cria o índice BM25 (A outra parte LENTA)
        print("INFO: Criando o índice BM25Retriever a partir dos documentos...")
        keyword_retriever = BM25Retriever.from_documents(docs_list)
        keyword_retriever.k = 3 # Garante que o k seja salvo no objeto
        print("INFO: Índice BM25 criado com sucesso.")

        # 5. Salva o objeto em um arquivo .pkl
        with open(OUTPUT_FILE, "wb") as f:
            pickle.dump(keyword_retriever, f)

        print("\n" + "="*30)
        print(f"✅ SUCESSO! Índice salvo em: {OUTPUT_FILE}")
        print("="*30)

    except Exception as e:
        print(f"❌ ERRO CRÍTICO durante o build: {e}")

if __name__ == "__main__":
    build_and_save_index()