import os
import shutil
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- CONFIGURAÇÃO DE CAMINHOS ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
CHROMA_PATH = os.path.join(BACKEND_DIR, "chroma_db_local")
DATA_DIR = os.path.join(BACKEND_DIR, "data")


# --- FUNÇÕES DE CARREGAMENTO DE DADOS ---

def load_and_split_refined_faqs():
    """
    Lê os arquivos `refinado_*.txt`, extrai a URL do vídeo do cabeçalho,
    e cria um Document (chunk) para cada par de Pergunta/Resposta.
    """
    print("\nINFO: Processando arquivos de FAQ refinados (refinado_*.txt)...")
    faq_chunks = []
    refined_files = [f for f in os.listdir(DATA_DIR) if f.startswith("refinado_") and f.lower().endswith(".txt")]

    for file in refined_files:
        file_path = os.path.join(DATA_DIR, file)
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # MUDANÇA: Extrai a URL do cabeçalho e separa o conteúdo
        video_source_url = "URL_NAO_ENCONTRADA"
        content_text = ""
        if lines and lines[0].startswith("VIDEO_SOURCE:"):
            video_source_url = lines[0].replace("VIDEO_SOURCE:", "").strip()
            content_text = "".join(lines[1:])
        else:
            content_text = "".join(lines)

        qa_pairs = content_text.strip().split("\nP: ")
        if qa_pairs and qa_pairs[0].startswith("P: "):
            qa_pairs[0] = qa_pairs[0][3:]

        pair_count = 0
        for pair in qa_pairs:
            if "R:" in pair:
                try:
                    question, answer = pair.split("\nR:", 1)
                    content = f"P: {question.strip()}\nR: {answer.strip()}"
                    # MUDANÇA: Adiciona a URL do vídeo aos metadados de cada chunk
                    metadata = {'source_file': file, 'type': 'faq_video', 'source_video': video_source_url}
                    faq_chunks.append(Document(page_content=content, metadata=metadata))
                    pair_count += 1
                except ValueError:
                    print(f"    -> AVISO: Formato P/R inesperado no arquivo {file} no trecho: '{pair[:50]}...'")

        print(f"  -> O arquivo '{file}' foi dividido em {pair_count} chunks de Pergunta/Resposta.")

    return faq_chunks


def load_and_split_manuals_data():
    all_manual_chunks = []
    manual_txt_files = [f for f in os.listdir(DATA_DIR) if
                        f.lower().endswith('.txt') and not f.startswith("refinado_")]
    if not manual_txt_files:
        print("\nINFO: Nenhum arquivo .txt de MANUAL encontrado para processar.")
        return []

    print(f"\nINFO: Encontrados {len(manual_txt_files)} arquivos .txt para processar como MANUAIS.")
    headers_to_split_on = [("##", "Header 2")]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)

    for txt_file in manual_txt_files:
        print(f"  -> Processando e dividindo o manual: {txt_file}")
        file_path = os.path.join(DATA_DIR, txt_file)
        with open(file_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        chunks = markdown_splitter.split_text(full_text)
        for chunk in chunks:
            # MUDANÇA: Renomeado para 'source_file' para consistência
            chunk.metadata['source_file'] = txt_file
            chunk.metadata['type'] = 'manual'
        all_manual_chunks.extend(chunks)
        print(f"    -> O arquivo '{txt_file}' foi dividido em {len(chunks)} chunks lógicos.")
    return all_manual_chunks


# --- FUNÇÃO PRINCIPAL (sem alterações) ---
def create_database():
    print("\nIniciando a CRIAÇÃO do Banco de Vetores (RAG)...")
    faq_chunks = load_and_split_refined_faqs()
    manual_chunks = load_and_split_manuals_data()
    all_chunks = faq_chunks + manual_chunks
    if not all_chunks:
        print("\nAVISO: Nenhum chunk de dados encontrado para processar. Verifique sua pasta /data.")
        return

    print(f"\nINFO: Total de {len(all_chunks)} chunks para serem adicionados ao DB.")
    print("INFO: Gerando embeddings com o modelo do Google 'text-embedding-004'...")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key: raise ValueError("ERRO: Chave de API do Google não encontrada.")
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    if os.path.exists(CHROMA_PATH):
        print(f"INFO: Apagando banco de dados antigo em '{CHROMA_PATH}'...")
        shutil.rmtree(CHROMA_PATH)
    print(f"INFO: Criando novo DB vetorial em '{CHROMA_PATH}'...")
    db = Chroma.from_documents(all_chunks, embeddings_model, persist_directory=CHROMA_PATH)
    print("\n✅ SUCESSO! O Banco de Vetores (RAG) foi criado/atualizado com sucesso!")


if __name__ == "__main__":
    load_dotenv()
    create_database()