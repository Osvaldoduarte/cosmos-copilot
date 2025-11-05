# Em backend/scripts/gerenciar_pipeline.py
# (SUBSTITUA o conteúdo deste arquivo)

import os
import shutil
import json
import traceback
import subprocess
import argparse
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from typing import List, Dict  # Necessário para a classe RefinedData
from pydantic import BaseModel, Field  # A causa do NameError anterior

from dotenv import load_dotenv


# Define o caminho absoluto para a raiz do backend (um nível acima de 'scripts')
APP_DIR = Path(__file__).parent.parent.resolve()
env_path = APP_DIR / ".env"

if not env_path.exists():
    print(f"⚠️  Atenção [gerenciar_pipeline]: Arquivo .env não encontrado em {env_path}")
else:
    load_dotenv(dotenv_path=env_path)
    print(f"✅ [gerenciar_pipeline] Variáveis de ambiente carregadas de: {env_path}")
# --- Fim da Correção ---

import whisper
import fitz  # PyMuPDF
from langchain.docstore.document import Document
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
import chromadb
from chromadb.utils.embedding_functions import GoogleGenerativeAiEmbeddingFunction
from pytube import YouTube

# --- 1. CONFIGURAÇÕES E CONSTANTES GLOBAIS ---
DATA_DIR = APP_DIR / "data"
VIDEOS_DIR = APP_DIR / "videos"
LINKS_FILE = APP_DIR / "scripts" / "youtube_links.txt"
TEMP_DIR = APP_DIR / "temp_audio"

CHROMA_HOST = os.environ.get("CHROMA_HOST")
CHROMA_DB_PATH = APP_DIR / "chroma_db_local"


def get_chroma_client():
    """
    Inicializa e retorna o destino do cliente ChromaDB (local ou remoto).
    (Esta função agora espelha a lógica de conexão do main.py)
    """
    if CHROMA_HOST:
        print(f"\nINFO: Conectando ao ChromaDB REMOTO em: {CHROMA_HOST}")
        try:
            url_to_parse = CHROMA_HOST
            if not url_to_parse.startswith(('http://', 'https://')):
                url_to_parse = 'https://' + url_to_parse

            parsed_url = urlparse(url_to_parse)
            host = parsed_url.netloc.split(':')[0] if parsed_url.netloc else parsed_url.path.split(':')[0]
            ssl_enabled = parsed_url.scheme == 'https'
            port = parsed_url.port or (443 if ssl_enabled else 80)

            if not host:
                raise ValueError("Host não encontrado na CHROMA_HOST URL.")

            print(f"INFO: Usando HttpClient com host='{host}', port={port}, ssl={ssl_enabled}")

            client = chromadb.HttpClient(
                host=host,
                ssl=ssl_enabled,
                port=port
            )
            client.heartbeat()  # Testa a conexão
            print("INFO: Conexão com ChromaDB remoto bem-sucedida.")
            return client
        except Exception as e:
            print(f"❌ ERRO FATAL ao conectar ao ChromaDB remoto: {e}")
            traceback.print_exc()
            raise
    else:
        print(f"\nINFO: Usando ChromaDB LOCAL em: {CHROMA_DB_PATH}")
        return chromadb.PersistentClient(path=str(CHROMA_DB_PATH))


# --- 2. FUNÇÕES DO PIPELINE (Extração, Transcrição, etc.) ---

def get_video_id(video_url: str) -> str:
    """Extrai o ID do vídeo de vários formatos de URL do YouTube."""
    try:
        if 'youtu.be' in video_url:
            return video_url.split('/')[-1].split('?')[0]
        if 'watch' in video_url:
            query = urlparse(video_url).query
            return parse_qs(query)['v'][0]
    except Exception as e:
        print(f"  AVISO: Não foi possível extrair o ID do vídeo da URL: {video_url} (Erro: {e})")
    return ""


def download_audio(video_url: str, video_id: str) -> Path | None:
    """Baixa o áudio de um vídeo do YouTube."""
    try:
        yt = YouTube(video_url)
        audio_stream = yt.streams.filter(only_audio=True).first()
        if not audio_stream:
            print(f"  ERRO: Nenhum stream de áudio encontrado para {video_id}")
            return None

        print(f"  Baixando áudio para: {yt.title}...")
        downloaded_file = audio_stream.download(output_path=TEMP_DIR, filename=f"{video_id}.mp4")
        return Path(downloaded_file)
    except Exception as e:
        print(f"  ERRO durante o download do áudio para {video_id}: {e}")
        return None


def transcribe_audio(audio_path: Path, model) -> dict:
    """Transcreve um arquivo de áudio usando o Whisper."""
    try:
        print(f"  Transcrevendo áudio... (Isso pode levar alguns minutos)")
        result = model.transcribe(str(audio_path), language="pt", fp16=False, verbose=False)
        return result
    except Exception as e:
        print(f"  ERRO durante a transcrição do áudio {audio_path.name}: {e}")
        traceback.print_exc()
        return {}


def process_text_file(file_path: Path) -> Path:
    """ Lê um arquivo .txt e o salva em formato .jsonl para refinamento. """
    print(f"  Processando arquivo de texto: {file_path.name}")
    try:
        with file_path.open('r', encoding='utf-8') as f:
            content = f.read()

        json_data = {
            "source_type": "documento_texto",
            "source_name": file_path.name,
            "content": content
        }

        output_filename = f"processado_{file_path.stem}.jsonl"
        output_path = DATA_DIR / output_filename

        with output_path.open('w', encoding='utf-8') as f:
            f.write(json.dumps(json_data, ensure_ascii=False) + "\n")

        print(f"  -> Arquivo de texto salvo em {output_filename}")
        return output_path
    except Exception as e:
        print(f"  ERRO ao processar {file_path.name}: {e}")
        return None


def process_pdf_file(file_path: Path) -> Path:
    """ Lê um arquivo .pdf, extrai o texto e o salva em formato .jsonl. """
    print(f"  Processando arquivo PDF: {file_path.name}")
    try:
        doc = fitz.open(file_path)
        full_text = ""
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            full_text += page.get_text() + "\n"
        doc.close()

        json_data = {
            "source_type": "documento_pdf",
            "source_name": file_path.name,
            "content": full_text
        }

        output_filename = f"processado_{file_path.stem}.jsonl"
        output_path = DATA_DIR / output_filename

        with output_path.open('w', encoding='utf-8') as f:
            f.write(json.dumps(json_data, ensure_ascii=False) + "\n")

        print(f"  -> PDF salvo em {output_filename}")
        return output_path
    except Exception as e:
        print(f"  ERRO ao processar {file_path.name}: {e}")
        return None


def get_refiner_chain(api_key):
    """Inicializa a cadeia de IA (LLM) para refinamento de dados."""

    # 💡 CORREÇÃO 1: Alterado o nome do modelo para um válido
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0.1)

    # (Definição da Pydantic para a saída estruturada)
    class RefinedData(BaseModel):  # <-- Esta linha agora funciona
        perguntas_respostas: List[Dict[str, str]] = Field(
            description="Uma lista de pares de pergunta e resposta extraídos do texto.")
        palavras_chave: List[str] = Field(description="Uma lista de palavras-chave relevantes.")

    # (Prompt Template)
    prompt_template = """
    Você é um especialista em processamento de dados para um sistema de RAG (Retrieval-Augmented Generation).
    Sua tarefa é ler o conteúdo bruto fornecido e extraí-lo em um formato JSON estruturado.

    Regras:
    1.  O conteúdo será uma transcrição de vídeo, um documento de texto ou um PDF.
    2.  Seu objetivo é identificar e formular pares claros de "Pergunta" e "Resposta" com base no conteúdo.
    3.  Gere o máximo de pares P/R que puder, desde que sejam factuais ao texto.
    4.  Crie uma lista de palavras-chave (keywords) que resumem os tópicos principais.

    Conteúdo Bruto:
    ---
    {content}
    ---

    Gere a saída JSON estruturada de acordo com o formato solicitado.
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    parser = JsonOutputParser(pydantic_object=RefinedData)

    return prompt | llm | parser


def refine_single_json_file(jsonl_path: Path, chain, source_type: str):
    """Lê um arquivo .jsonl, passa pela IA e salva o resultado .jsonl refinado."""
    print(f"  Refinando: {jsonl_path.name}...")
    try:
        with jsonl_path.open('r', encoding='utf-8') as f:
            line = f.readline()
            if not line:
                print(f"  AVISO: Arquivo {jsonl_path.name} está vazio. Pulando.")
                return

            data = json.loads(line)
            content_to_refine = data.get("content", "")

            if not content_to_refine.strip():
                print(f"  AVISO: Conteúdo em {jsonl_path.name} está vazio. Pulando.")
                return

        # Invoca a cadeia de IA
        refined_output = chain.invoke({"content": content_to_refine})

        # Define o caminho de saída
        output_filename = f"refinado_{jsonl_path.stem.replace('processado_', '')}.jsonl"
        output_path = DATA_DIR / output_filename

        # Salva a saída refinada
        with output_path.open('w', encoding='utf-8') as f:
            # Salva metadados importantes no início do arquivo
            metadata_header = {
                "source_file": data.get("source_name", "desconhecido"),
                "source_type": source_type,
                "video_url": data.get("video_url", None)  # Propaga a URL do vídeo
            }
            f.write(json.dumps(metadata_header, ensure_ascii=False) + "\n")

            # Salva os pares de P/R
            for qa_pair in refined_output.get("perguntas_respostas", []):
                f.write(json.dumps(qa_pair, ensure_ascii=False) + "\n")

        print(f"  -> Refinamento salvo em {output_filename}")

    except OutputParserException as ope:
        print(
            f"  ERRO DE PARSING DA IA: Falha ao refinar {jsonl_path.name}. A saída da IA pode estar mal formatada. {ope}")
    except Exception as e:
        print(f"  ERRO ao refinar {jsonl_path.name}: {e}")
        traceback.print_exc()


# --- 3. FUNÇÃO DE ORQUESTRAÇÃO (main) ---
def main(full_rebuild=False):
    print("--- INICIANDO PIPELINE DE INGESTÃO DE DADOS ---")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ ERRO: GEMINI_API_KEY não configurada.")
        print("   Por favor, adicione-a ao seu arquivo .env e tente novamente.")
        return

    # --- Etapa 1: Inicializar o Refinador (IA) ---
    print("\n--- INICIANDO ETAPA DE REFINAMENTO (IA) ---")
    try:
        refiner_chain = get_refiner_chain(api_key)
        print("✅ Refinador de IA (Gemini) inicializado.")
    except Exception as e:
        print(f"❌ ERRO FATAL ao inicializar a IA (Verifique sua GEMINI_API_KEY): {e}")
        traceback.print_exc()
        return

    # --- Etapa 2: Processar Vídeos (se houver) ---
    json_paths_to_refine = []

    # 💡 CORREÇÃO 2: Só executa a transcrição se --full-rebuild for solicitado
    if LINKS_FILE.exists():
        if full_rebuild:
            print(f"\n--- INICIANDO ETAPA DE TRANSCRIÇÃO (Vídeos) --full-rebuild ATIVADO ---")
            try:
                from transcribe_videos import transcribe_youtube_videos
                transcribe_youtube_videos()
            except Exception as e:
                print(f"❌ ERRO durante a etapa de transcrição: {e}")
                traceback.print_exc()
        else:
            print(f"\nINFO: Pulando etapa de transcrição de vídeos (cache). Use --full-rebuild para forçar.")
    else:
        print("\nINFO: Arquivo 'youtube_links.txt' não encontrado. Pulando etapa de transcrição.")

    # Coleta JSONs de transcrição (se existirem na pasta /data)
    transcript_files = list(DATA_DIR.glob("transcricao_*.json"))
    for tf in transcript_files:
        try:
            # Verifica se o arquivo refinado já existe E não estamos forçando
            refined_output_path = DATA_DIR / f"refinado_{tf.stem.replace('transcricao_', '')}.jsonl"
            if refined_output_path.exists() and not full_rebuild:
                print(f"  AVISO: [Cache] Arquivo refinado para {tf.name} já existe. Pulando refinamento.")
                continue  # Pula para o próximo arquivo de transcrição

            with tf.open('r', encoding='utf-8') as f:
                transcription_data = json.load(f)

            full_text = " ".join([segment['text'] for segment in transcription_data if 'text' in segment])
            video_url = transcription_data[0].get('video_name', '') if transcription_data else ''

            json_data = {
                "source_type": "video_transcricao",
                "source_name": tf.name,
                "content": full_text,
                "video_url": video_url
            }

            output_filename = f"processado_{tf.stem.replace('transcricao_', '')}.jsonl"
            output_path = DATA_DIR / output_filename

            with output_path.open('w', encoding='utf-8') as f:
                f.write(json.dumps(json_data, ensure_ascii=False) + "\n")

            json_paths_to_refine.append({'path': output_path, 'type': 'video'})

        except Exception as e:
            print(f"  ERRO ao pré-processar o arquivo de transcrição {tf.name}: {e}")

    # --- Etapa 3: Processar Documentos Locais (PDF, TXT) ---
    print(f"\n--- INICIANDO ETAPA DE PROCESSAMENTO (Documentos) ---")
    document_files = [f for f in DATA_DIR.iterdir() if f.is_file() and f.suffix in ['.txt', '.pdf']]
    if not document_files:
        print("INFO: Nenhum arquivo .txt ou .pdf encontrado na pasta /data.")
    else:
        for index, doc_file in enumerate(document_files):
            print(f"  --- Processando Documento {index + 1}/{len(document_files)}: {doc_file.name} ---")

            # Lógica para 'full-rebuild'
            refined_output_path = DATA_DIR / f"refinado_{doc_file.stem}.jsonl"
            if refined_output_path.exists() and not full_rebuild:
                print(f"  AVISO: [Cache] Arquivo refinado para {doc_file.name} já existe. Pulando refinamento.")
                continue

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
    print(f"\nDEBUG: JSONs a serem refinados: {[source['path'].name for source in json_paths_to_refine]}")
    if json_paths_to_refine:
        print(f"\n--- INICIANDO ETAPA DE REFINAMENTO PARA {len(json_paths_to_refine)} FONTES ---")
        for source in json_paths_to_refine:
            refine_single_json_file(source['path'], refiner_chain, source['type'])
    elif not full_rebuild:
        print("INFO: Nenhum arquivo novo para refinar. Cache de refinamento está completo.")

    # --- Etapa 5: Criar o banco de dados final ---
    print("\nDEBUG: Verificando arquivos .jsonl antes de criar DB...")
    jsonl_files_debug = list(DATA_DIR.glob("refinado_*.jsonl"))
    print(f"DEBUG: Arquivos .jsonl encontrados em {DATA_DIR}: {len(jsonl_files_debug)}")

    if jsonl_files_debug:
        try:
            # Importa e executa o script de criação do DB
            from create_db import create_database
            create_database()
        except Exception as e:
            print(f"❌ ERRO FATAL durante a criação do banco de dados: {e}")
            traceback.print_exc()
    else:
        print("\nAVISO: Nenhum arquivo de dados refinado (.jsonl) encontrado. O banco de dados não será criado.")

    print("\n--- PIPELINE CONCLUÍDO COM SUCESSO! ---")


# --- 4. EXECUTOR ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline de Ingestão de Dados para o Cosmos Copilot.")
    parser.add_argument(
        '--full-rebuild',
        action='store_true',
        help="Força o reprocessamento de todos os arquivos, ignorando caches."
    )
    args = parser.parse_args()

    main(full_rebuild=args.full_rebuild)