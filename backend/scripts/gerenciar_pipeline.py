import os
import shutil
import json
import subprocess
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import whisper
from dotenv import load_dotenv

from langchain.docstore.document import Document
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# --- 1. CONFIGURAÇÕES E CONSTANTES GLOBAIS ---
BACKEND_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
CHROMA_PATH = str(BACKEND_DIR / "chroma_db_local")
LINKS_FILE = BACKEND_DIR / "youtube_links.txt"
TEMP_DIR = BACKEND_DIR / "temp_audio"
REFINER_PROMPT_JSON_TEMPLATE = """
Você é um sistema especialista em ETL... (use seu prompt completo aqui)
"""
REFINER_PROMPT_JSON = ChatPromptTemplate.from_template(REFINER_PROMPT_JSON_TEMPLATE)


# --- 2. FUNÇÕES DO PIPELINE ---
def transcribe_single_video(url: str, model) -> Path | None:
    try:
        video_id = parse_qs(urlparse(url).query)['v'][0]
        json_path = DATA_DIR / f"youtube_{video_id}.json"
        if json_path.exists():
            print(f"  -> ⏭️  Transcrição já existe para '{url}'. Pulando.")
            return json_path
        audio_filepath = TEMP_DIR / f"{video_id}.mp3"
        print(f"  -> 🎤 Baixando e transcrevendo áudio...")
        command = ['yt-dlp', '-x', '--audio-format', 'mp3', '-o', str(audio_filepath), url]
        subprocess.run(command, check=True, timeout=300)
        if not audio_filepath.exists(): raise FileNotFoundError("Download do áudio falhou.")
        result = model.transcribe(str(audio_filepath), verbose=False, language="pt")
        output_data = [{"text": seg["text"].strip(), "start": seg["start"], "end": seg["end"], "video_name": url} for
                       seg in result["segments"]]
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        print(f"  -> ✅ Transcrição salva em '{json_path.name}'")
        return json_path
    except Exception as e:
        print(f"  -> ❌ ERRO ao transcrever a URL '{url}': {e}")
        return None
    finally:
        if 'audio_filepath' in locals() and audio_filepath.exists(): os.remove(audio_filepath)


def refine_single_json_file(json_filepath: Path, chain, source_type: str):
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
        video_url = segments[0].get("video_name", "URL_NAO_ENCONTRADA")
        total_chunks_created = 0
        SEGMENTS_PER_BLOCK = 15
        with open(output_filepath, 'w', encoding='utf-8') as f:
            for i in range(0, len(segments), SEGMENTS_PER_BLOCK):
                block_segments = segments[i:i + SEGMENTS_PER_BLOCK]
                block_text = " ".join([seg['text'] for seg in block_segments])
                block_start_time = block_segments[0]['start']
                block_end_time = block_segments[-1]['end']

                refined_data_list = chain.invoke({"transcription_text": block_text})
                if not isinstance(refined_data_list, list) or not refined_data_list: continue

                for chunk_data in refined_data_list:
                    chunk_id = f"{json_filepath.stem}_{i}_{refined_data_list.index(chunk_data)}"
                    final_chunk = {
                        "chunk_id": chunk_id, "source_document_id": json_filepath.stem,
                        "title": chunk_data.get("title", "Sem Título"), "content": chunk_data.get("content", ""),
                        "metadata": {
                            "source_type": source_type,
                            "source_url": video_url,
                            "start_time": round(block_start_time), "end_time": round(block_end_time),
                            "module": chunk_data.get("module", "Geral"),
                            "tags": chunk_data.get("tags", [])
                        }
                    }
                    f.write(json.dumps(final_chunk, ensure_ascii=False) + '\n')
                    total_chunks_created += 1

        print(f"  -> ✅ {total_chunks_created} chunks salvos em: '{output_filepath.name}'")
        print(f"  -> 💾 Arquivo de transcrição original '{json_filepath.name}' mantido como cache.")
    except Exception as e:
        print(f"  -> ❌ ERRO ao refinar o arquivo '{json_filepath.name}': {e}")


def create_database_from_all_jsonl():
    print("\n--- [FINAL] CRIANDO O BANCO DE DADOS VETORIAL ---")
    all_chunks = []
    jsonl_files = list(DATA_DIR.glob("refinado_*.jsonl"))
    if not jsonl_files:
        print("AVISO: Nenhum arquivo .jsonl encontrado.")
        return
    for file_path in jsonl_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                if "tags" in data["metadata"] and isinstance(data["metadata"]["tags"], list):
                    data["metadata"]["tags"] = ", ".join(data["metadata"]["tags"])
                doc = Document(page_content=data["content"],
                               metadata={**data["metadata"], "chunk_id": data["chunk_id"], "title": data["title"]})
                all_chunks.append(doc)

    if not all_chunks:
        print("\nAVISO: Nenhum chunk extraído.")
        return

    print(f"INFO: Total de {len(all_chunks)} chunks para adicionar ao DB.")
    api_key = os.environ.get("GEMINI_API_KEY")
    embeddings_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=api_key)

    if os.path.exists(CHROMA_PATH): shutil.rmtree(CHROMA_PATH)
    db = Chroma(persist_directory=CHROMA_PATH, embedding_function=embeddings_model)
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        batch_chunks = all_chunks[i:i + batch_size]
        db.add_documents(batch_chunks)
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
        print("INFO: Limpando arquivos .jsonl antigos...")
        deleted_files_count = 0
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".jsonl"):
                os.remove(DATA_DIR / filename)
                deleted_files_count += 1
        print(f"INFO: {deleted_files_count} arquivos .jsonl removidos.")

    DATA_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)

    try:
        print("INFO: Carregando modelos de IA (Whisper e Gemini)...")
        whisper_model = whisper.load_model("base")
        api_key = os.environ.get("GEMINI_API_KEY")
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=api_key, temperature=0.1)
        refiner_chain = REFINER_PROMPT_JSON | llm | JsonOutputParser()
        print("✅ Modelos carregados.")
    except Exception as e:
        print(f"❌ ERRO CRÍTICO na inicialização dos modelos: {e}")
        return

    if not LINKS_FILE.exists():
        print(f"❌ ERRO: 'youtube_links.txt' não encontrado.")
        return

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

    print(f"\n--- INICIANDO PROCESSAMENTO DE {len(video_sources)} VÍDEOS ---")
    for index, source in enumerate(video_sources):
        print(f"\n--- Processando Vídeo {index + 1}/{len(video_sources)}: {source['url']} (Tipo: {source['type']}) ---")

        json_path = transcribe_single_video(source['url'], whisper_model)
        if json_path:
            refine_single_json_file(json_path, refiner_chain, source['type'])

    create_database_from_all_jsonl()

    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)

    print("\n--- PIPELINE CONCLUÍDO COM SUCESSO! ---")


if __name__ == "__main__":
    main()