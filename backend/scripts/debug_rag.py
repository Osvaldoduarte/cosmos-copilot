import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- Configuração ---
BASE_DIR = Path(__file__).parent.parent.resolve()
ENV_PATH = BASE_DIR / ".env"
CHROMA_PATH_LOCAL = str(BASE_DIR / "chroma_db_local")

load_dotenv(ENV_PATH)
api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ ERRO: Chave de API não encontrada.")
    sys.exit(1)


def testar_cerebro():
    print(f"🧠 Acessando o cérebro em: {CHROMA_PATH_LOCAL}")

    # 1. Carrega o Banco
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    db = Chroma(persist_directory=CHROMA_PATH_LOCAL, embedding_function=embeddings, collection_name="evolution")

    # 2. Faz a Pergunta de Teste
    pergunta = "Quais tipos de contas o sistema controla?"
    print(f"\n🔍 Pergunta: '{pergunta}'")
    print("-" * 50)

    # 3. Busca os 3 trechos mais relevantes
    docs = db.similarity_search(pergunta, k=3)

    if not docs:
        print("❌ Nada encontrado! O banco parece vazio.")
    else:
        for i, doc in enumerate(docs):
            print(f"\n📄 Resultado #{i + 1}:")
            print(f"   Fonte: {doc.metadata.get('source_name')}")
            print(f"   Conteúdo: {doc.page_content[:200]}...")  # Mostra só o começo

            # Verifica se achou a palavra chave
            if "cartão de crédito" in doc.page_content.lower():
                print("   ✅ SUCESSO! Encontrou a menção a 'cartão de crédito'!")


if __name__ == "__main__":
    testar_cerebro()