import os
import shutil
import json
import subprocess
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import whisper
import fitz  # PyMuPDF --- NOVO ---
from dotenv import load_dotenv

from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException

# --- 1. CONFIGURAÇÕES E CONSTANTES GLOBAIS ---
BACKEND_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
VIDEOS_DIR = BACKEND_DIR / "videos"
CHROMA_PATH = str(BACKEND_DIR / "chroma_db_local")
LINKS_FILE = BACKEND_DIR / "youtube_links.txt"
TEMP_DIR = BACKEND_DIR / "temp_audio"
REFINER_PROMPT_JSON_TEMPLATE = """
Você é um sistema especialista em ETL (Extração, Transformação e Carga) de conhecimento. Sua função é receber um trecho de uma transcrição de vídeo-aula ou um texto de um documento e transformá-lo em um ou mais "chunks" de conhecimento em formato JSON. Cada chunk deve ser atômico, coeso e focado em um único tópico ou subtópico. O objetivo é criar uma base de dados vetorial otimizada para buscas de similaridade (RAG).

**Instruções Detalhadas:**

1.  **Analise o Texto:** Leia o conteúdo fornecido e identifique os principais conceitos, explicações, exemplos ou instruções.
2.  **Segmente em Chunks:** Divida o texto em segmentos lógicos. Um único bloco de texto pode se tornar um ou vários chunks, dependendo da densidade da informação.
3.  **Gere Títulos Curtos e Descritivos:** Para cada chunk, crie um `title` que resuma o conteúdo de forma clara e concisa (máximo de 10 palavras).
4.  **Formate o Conteúdo:** O campo `content` deve ser o texto do chunk, otimizado para clareza.
5.  **Defina o Módulo:** No campo `module`, categorize o chunk em uma das seguintes áreas de conhecimento: "Vendas", "Produto", "Marketing", "Negociação", "Geral".
6.  **Atribua Tags:** No campo `tags`, forneça uma lista de 3 a 5 palavras-chave relevantes.
7.  **Estrutura de Saída:** Sua saída DEVE ser uma lista de objetos JSON.

**Exemplo de Saída JSON Esperada (DEVE ser uma lista):**
[
  {{
    "title": "Qualificação de Leads com BANT",
    "content": "A qualificação de leads é um processo crucial em vendas. Uma metodologia eficaz é o BANT, que avalia quatro critérios principais: Budget (Orçamento), Authority (Autoridade), Need (Necessidade) e Timeline (Prazo).",
    "module": "Vendas",
    "tags": ["BANT", "qualificação", "lead", "budget", "vendas"]
  }},
  {{
    "title": "Análise de Concorrência em Vendas",
    "content": "Para um posicionamento estratégico eficaz, é fundamental realizar o mapeamento da concorrência, identificando tanto os concorrentes diretos quanto os indiretos.",
    "module": "Negociação",
    "tags": ["concorrência", "análise de mercado", "posicionamento", "estratégia"]
  }}
]

**Conteúdo para Processar:**
{transcription_text}
"""
REFINER_PROMPT_JSON = ChatPromptTemplate.from_template(REFINER_PROMPT_JSON_TEMPLATE)


# --- 2. FUNÇÕES DO PIPELINE ---

def transcribe_youtube_video(url: str, model) -> Path | None:
    # ... (código inalterado)
    try:
        video_id = parse_qs(urlparse(url).query)['v'][0]
        json_path = DATA_DIR / f"youtube_{video_id}.json"
        if json_path.exists():
            print(f"  -> ⏭️  Transcrição (YouTube) já existe para '{url}'. Pulando.")
            return json_path
        TEMP_DIR.mkdir(exist_ok=True)
        audio_filepath = TEMP_DIR / f"{video_id}.mp3"
        print(f"  -> 🎤 Baixando e transcrevendo áudio (YouTube)...")
        command = ['yt-dlp', '-x', '--audio-format', 'mp3', '-o', str(audio_filepath), url]
        subprocess.run(command, check=True, timeout=300)
        if not audio_filepath.exists(): raise FileNotFoundError("Download do áudio falhou.")
        result = model.transcribe(str(audio_filepath), verbose=False, language="pt")
        output_data = [{"text": seg["text"].strip(), "source_name": url} for seg in result["segments"]]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"  -> ✅ Transcrição (YouTube) salva em '{json_path.name}'")
        return json_path
    except Exception as e:
        print(f"  -> ❌ ERRO ao transcrever a URL '{url}': {e}")
        return None
    finally:
        if 'audio_filepath' in locals() and audio_filepath.exists(): os.remove(audio_filepath)


def transcribe_local_video(video_path: Path, model) -> Path | None:
    # ... (código inalterado)
    try:
        video_id = video_path.stem
        json_path = DATA_DIR / f"local_{video_id}.json"
        if json_path.exists():
            print(f"  -> ⏭️  Transcrição (Local) já existe para '{video_path.name}'. Pulando.")
            return json_path
        print(f"  -> 🎤 Transcrevendo vídeo local: '{video_path.name}'...")
        result = model.transcribe(str(video_path), verbose=False, language="pt")
        output_data = [{"text": seg["text"].strip(), "source_name": video_path.name} for seg in result["segments"]]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"  -> ✅ Transcrição (Local) salva em '{json_path.name}'")
        return json_path
    except Exception as e:
        print(f"  -> ❌ ERRO ao transcrever o vídeo local '{video_path.name}': {e}")
        return None


# --- NOVO ---: Funções para processar arquivos TXT e PDF
def process_text_file(file_path: Path) -> Path | None:
    """Lê um arquivo .txt e o converte para o formato JSON intermediário."""
    try:
        file_id = file_path.stem
        json_path = DATA_DIR / f"doc_{file_id}.json"
        if json_path.exists():
            print(f"  -> ⏭️  Processamento de texto já existe para '{file_path.name}'. Pulando.")
            return json_path

        print(f"  -> 📄 Processando arquivo de texto: '{file_path.name}'...")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Estrutura como um único "segmento" para compatibilidade com a função de refinamento
        output_data = [{"text": content.strip(), "source_name": file_path.name}]

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"  -> ✅ Processamento de texto salvo em '{json_path.name}'")
        return json_path
    except Exception as e:
        print(f"  -> ❌ ERRO ao processar o arquivo de texto '{file_path.name}': {e}")
        return None


def process_pdf_file(file_path: Path) -> Path | None:
    """Lê um arquivo .pdf, extrai o texto e o converte para o formato JSON intermediário."""
    try:
        file_id = file_path.stem
        json_path = DATA_DIR / f"doc_{file_id}.json"
        if json_path.exists():
            print(f"  -> ⏭️  Processamento de PDF já existe para '{file_path.name}'. Pulando.")
            return json_path

        print(f"  -> 📄 Processando arquivo PDF: '{file_path.name}'...")
        doc = fitz.open(file_path)
        content = ""
        for page in doc:
            content += page.get_text()
        doc.close()

        output_data = [{"text": content.strip(), "source_name": file_path.name}]

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"  -> ✅ Processamento de PDF salvo em '{json_path.name}'")
        return json_path
    except Exception as e:
        print(f"  -> ❌ ERRO ao processar o arquivo PDF '{file_path.name}': {e}")
        return None


def refine_single_json_file(json_filepath: Path, chain, source_type: str):
    # ... (código inalterado)
    if not json_filepath or not json_filepath.exists(): return
    output_filepath = DATA_DIR / f"refinado_{json_filepath.stem}.jsonl"
    if output_filepath.exists():
        print(f"  -> ⏭️  Arquivo refinado '{output_filepath.name}' já existe. Pulando refinamento.")
        return
    try:
        print(f"  -> 🧠 Refinando {json_filepath.name} com IA...")
        with open(json_filepath, 'r', encoding='utf-8') as f:
            segments = json.load(f)
        if not segments: return
        source_name = segments[0].get("source_name", "Fonte Desconhecida")
        total_chunks_created = 0

        # --- NOVO ---: Lógica adaptada para documentos e vídeos
        # Para documentos, processamos o texto inteiro. Para vídeos, em blocos.
        if "start" in segments[0]:  # Heurística para detectar se é de vídeo
            SEGMENTS_PER_BLOCK = 15
        else:  # Se for documento, processar tudo de uma vez
            SEGMENTS_PER_BLOCK = len(segments)

        with open(output_filepath, 'w', encoding='utf-8') as f:
            for i in range(0, len(segments), SEGMENTS_PER_BLOCK):
                block_segments = segments[i:i + SEGMENTS_PER_BLOCK]
                block_text = " ".join([seg['text'] for seg in block_segments])

                try:
                    refined_data_list = chain.invoke({"transcription_text": block_text})
                except (OutputParserException, json.JSONDecodeError) as e:
                    print(f"  -> ⚠️ AVISO: Falha ao analisar a resposta da IA para um bloco. Pulando. Erro: {e}")
                    continue

                if not isinstance(refined_data_list, list) or not refined_data_list: continue
                for idx, chunk_data in enumerate(refined_data_list):
                    chunk_id = f"{json_filepath.stem}_{i}_{idx}"
                    metadata = {
                        "source_type": source_type, "source_name": source_name,
                        "module": chunk_data.get("module", "Geral"),
                        "tags": chunk_data.get("tags", [])
                    }
                    # Adiciona metadados de tempo apenas se existirem
                    if "start" in block_segments[0]:
                        metadata["start_time"] = round(block_segments[0].get('start', 0))
                        metadata["end_time"] = round(block_segments[-1].get('end', 0))

                    final_chunk = {
                        "chunk_id": chunk_id, "source_document_id": json_filepath.stem,
                        "title": chunk_data.get("title", "Sem Título"),
                        "content": chunk_data.get("content", ""),
                        "metadata": metadata
                    }
                    f.write(json.dumps(final_chunk, ensure_ascii=False) + '\n')
                    total_chunks_created += 1
        print(f"  -> ✅ {total_chunks_created} chunks salvos em: '{output_filepath.name}'")
    except Exception as e:
        print(f"  -> ❌ ERRO GERAL ao refinar o arquivo '{json_filepath.name}': {e}")


def create_database_from_all_jsonl():
    # ... (código inalterado)
    print("\n--- [FINAL] CRIANDO O BANCO DE DADOS VETORIAL ---")
    all_chunks = []
    jsonl_files = list(DATA_DIR.glob("refinado_*.jsonl"))
    if not jsonl_files:
        print("AVISO: Nenhum arquivo .jsonl encontrado para criar o banco de dados.")
        return
    for file_path in jsonl_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "tags" in data["metadata"] and isinstance(data["metadata"]["tags"], list):
                        data["metadata"]["tags"] = ", ".join(data["metadata"]["tags"])
                    doc = Document(page_content=data["content"],
                                   metadata={**data["metadata"], "chunk_id": data["chunk_id"], "title": data["title"]})
                    all_chunks.append(doc)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"  -> ⚠️ AVISO: Pulando linha mal formada no arquivo '{file_path.name}'. Erro: {e}")
    if not all_chunks:
        print("\nAVISO: Nenhum chunk válido foi extraído para adicionar ao banco de dados.")
        return
    print(f"INFO: Total de {len(all_chunks)} chunks para adicionar ao DB.")
    api_key = os.environ.get("GEMINI_API_KEY")
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)
    if os.path.exists(CHROMA_PATH): shutil.rmtree(CHROMA_PATH)
    print("  -> Inicializando novo banco de dados ChromaDB...")
    db = Chroma.from_documents(
        documents=all_chunks,
        embedding=embeddings_model,
        persist_directory=CHROMA_PATH
    )
    print(f"  -> Adicionados {len(all_chunks)} chunks em uma única operação.")
    db.persist()
    print("✅ Banco de Dados criado/atualizado com sucesso!")


# --- 3. ORQUESTRADOR PRINCIPAL ---
def main():
    parser = argparse.ArgumentParser(description="Pipeline de gestão da base de conhecimento do RAG.")
    parser.add_argument('--full-rebuild', action='store_true',
                        help="Força a limpeza dos .jsonl e a recriação do conhecimento.")
    args = parser.parse_args()
    print("--- INICIANDO PIPELINE DE GESTÃO DA BASE DE CONHECIMENTO ---")
    load_dotenv()
    if args.full_rebuild:
        print("\n--- MODO RECONSTRUÇÃO COMPLETA ATIVADO ---")
        print("INFO: Limpando arquivos .jsonl e .json intermediários...")
        deleted_files_count = 0
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".jsonl") or (not filename.startswith("refinado_") and filename.endswith(".json")):
                os.remove(DATA_DIR / filename)
                deleted_files_count += 1
        print(f"INFO: {deleted_files_count} arquivos removidos.")
    DATA_DIR.mkdir(exist_ok=True)
    VIDEOS_DIR.mkdir(exist_ok=True)
    try:
        print("INFO: Carregando modelos de IA (Whisper e Gemini)...")
        whisper_model = whisper.load_model("base")
        api_key = os.environ.get("GEMINI_API_KEY")
        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0.1)
        refiner_chain = REFINER_PROMPT_JSON | llm | JsonOutputParser()
        print("✅ Modelos carregados.")
    except Exception as e:
        print(f"❌ ERRO CRÍTICO na inicialização dos modelos: {e}")
        return

    json_paths_to_refine = []

    # --- Etapa 1: Processar vídeos do YouTube ---
    # ... (código inalterado)
    if LINKS_FILE.exists():
        video_sources = []
        with open(LINKS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 1 and parts[0].startswith('http'):
                        url = parts[0]
                        source_type = parts[1].strip() if len(parts) > 1 else 'video_tutorial'
                        video_sources.append({'url': url, 'type': source_type})
        if video_sources:
            print(f"\n--- INICIANDO PROCESSAMENTO DE {len(video_sources)} VÍDEOS DO YOUTUBE ---")
            for index, source in enumerate(video_sources):
                print(
                    f"\n--- Processando Vídeo {index + 1}/{len(video_sources)}: {source['url']} (Tipo: {source['type']}) ---")
                json_path = transcribe_youtube_video(source['url'], whisper_model)
                if json_path:
                    json_paths_to_refine.append({'path': json_path, 'type': source['type']})

    # --- Etapa 2: Processar vídeos locais ---
    # ... (código inalterado)
    local_video_files = list(VIDEOS_DIR.glob("*.mp4")) + list(VIDEOS_DIR.glob("*.m4a")) + list(VIDEOS_DIR.glob("*.mov"))
    if local_video_files:
        print(f"\n--- INICIANDO PROCESSAMENTO DE {len(local_video_files)} VÍDEOS LOCAIS ---")
        for index, video_file in enumerate(local_video_files):
            print(f"\n--- Processando Vídeo Local {index + 1}/{len(local_video_files)}: {video_file.name} ---")
            source_type = 'video_local'
            json_path = transcribe_local_video(video_file, whisper_model)
            if json_path:
                json_paths_to_refine.append({'path': json_path, 'type': source_type})

    # --- NOVO ---: Etapa 3: Processar documentos TXT e PDF da pasta DATA
    document_files = list(DATA_DIR.glob("*.txt")) + list(DATA_DIR.glob("*.pdf"))
    if document_files:
        print(f"\n--- INICIANDO PROCESSAMENTO DE {len(document_files)} DOCUMENTOS LOCAIS ---")
        for index, doc_file in enumerate(document_files):
            print(f"\n--- Processando Documento {index + 1}/{len(document_files)}: {doc_file.name} ---")
            json_path = None
            source_type = ''
            if doc_file.suffix == '.txt':
                source_type = 'documento_texto'
                json_path = process_text_file(doc_file)
            elif doc_file.suffix == '.pdf':
                source_type = 'documento_pdf'
                json_path = process_pdf_file(doc_file)

            if json_path:
                json_paths_to_refine.append({'path': json_path, 'type': source_type})

    # --- Etapa 4: Refinar todos os JSONs coletados ---
    # ... (código inalterado)
    if json_paths_to_refine:
        print(f"\n--- INICIANDO ETAPA DE REFINAMENTO PARA {len(json_paths_to_refine)} FONTES ---")
        for source in json_paths_to_refine:
            refine_single_json_file(source['path'], refiner_chain, source['type'])

    # --- Etapa 5: Criar o banco de dados final ---
    create_database_from_all_jsonl()

    # --- Limpeza Final ---
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    print("\n--- PIPELINE CONCLUÍDO COM SUCESSO! ---")


if __name__ == "__main__":
    main()