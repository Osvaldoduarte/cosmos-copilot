# Em backend/scripts/transcribe_videos.py
# (SUBSTITUA o conteúdo deste arquivo)

import os
import json
import whisper
from pathlib import Path
from pytube import YouTube
import re

# --- 💡 CORREÇÃO: Bloco de 'load_dotenv' movido para o topo ---
from dotenv import load_dotenv

# Define o caminho absoluto para a raiz do backend (um nível acima de 'scripts')
BACKEND_DIR = Path(__file__).parent.parent.resolve()
env_path = BACKEND_DIR / ".env"

if not env_path.exists():
    print(f"⚠️  Atenção [transcribe]: Arquivo .env não encontrado em {env_path}")
else:
    load_dotenv(dotenv_path=env_path)
    print(f"✅ [transcribe] Variáveis de ambiente carregadas.")
# --- Fim da Correção ---


# --- CONFIGURAÇÃO DE CAMINHOS ---
DATA_DIR = BACKEND_DIR / "data"
# 💡 CORREÇÃO: O arquivo de links está na pasta 'scripts'
LINKS_FILE = BACKEND_DIR / "scripts" / "youtube_links.txt"
TEMP_DIR = BACKEND_DIR / "temp_audio"


def sanitize_filename(name):
    """Remove caracteres inválidos para nomes de arquivo."""
    return re.sub(r'[\\/*?:\"<>|]', "", name)


def transcribe_youtube_videos():
    """
    Função focada em ler o arquivo youtube_links.txt, transcrever os vídeos
    e salvar os resultados na pasta /data.
    """
    print("--- INICIANDO PROCESSO DE TRANSCRIÇÃO DE VÍDEOS DO YOUTUBE ---")

    # Garante que as pastas de saída e temporária existam
    DATA_DIR.mkdir(exist_ok=True)
    TEMP_DIR.mkdir(exist_ok=True)

    print("INFO: Carregando modelo Whisper... (Isso pode demorar na primeira vez)")
    model = whisper.load_model("base")
    print("✅ Modelo Whisper carregado com sucesso.")

    # --- Processar links do YouTube ---
    if not LINKS_FILE.exists():
        print(
            f"❌ ERRO: Arquivo 'youtube_links.txt' não encontrado em '{LINKS_FILE}'. Crie este arquivo com os links dos vídeos.")
        return

    with open(LINKS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    if not urls:
        print("INFO: 'youtube_links.txt' está vazio ou contém apenas comentários. Pulando transcrição.")
        return

    print(f"INFO: Encontrados {len(urls)} links de vídeo para processar.")

    for url in urls:
        try:
            yt = YouTube(url)

            # Remove caracteres inválidos do título para criar um nome de arquivo
            safe_title = sanitize_filename(yt.title)
            json_name = f"transcricao_{safe_title[:50]}.json"
            json_path = DATA_DIR / json_name

            if json_path.exists():
                print(f"⏭️  Pulando '{yt.title}', transcrição já existe.")
                continue

            print(f"\n⬇️  Baixando áudio de: '{yt.title}'...")
            audio_stream = yt.streams.filter(only_audio=True).first()
            downloaded_audio_path = audio_stream.download(output_path=str(TEMP_DIR))
            print("✅ Áudio baixado com sucesso.")

            print(f"🎤 Transcrevendo '{yt.title}'... (Isso pode levar alguns minutos)")
            result = model.transcribe(downloaded_audio_path, verbose=False, language="pt")

            output_data = []
            for segment in result["segments"]:
                output_data.append({
                    "text": segment["text"].strip(),
                    "start": segment["start"],
                    "end": segment["end"],
                    "video_name": url  # Salva a URL original
                })

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)

            print(f"✅ Transcrição de '{yt.title}' salva em '{json_path.name}'")

            # Limpa o arquivo de áudio temporário para economizar espaço
            os.remove(downloaded_audio_path)

        except Exception as e:
            print(f"❌ ERRO ao processar a URL '{url}': {e}")

    print("\n--- PROCESSO DE TRANSCRIÇÃO CONCLUÍDO ---")


if __name__ == "__main__":
    # O .env já foi carregado no topo.
    transcribe_youtube_videos()