# Arquivo: backend/scripts/transcribe_videos.py

import os
import json
import whisper
from pathlib import Path
from pytube import YouTube
import re

# --- CONFIGURAÇÃO DE CAMINHOS ---
BACKEND_DIR = Path(__file__).parent.parent.resolve()
DATA_DIR = BACKEND_DIR / "data"
LINKS_FILE = BACKEND_DIR / "youtube_links.txt"
TEMP_DIR = BACKEND_DIR / "temp_audio"


def sanitize_filename(name):
    """Remove caracteres inválidos para nomes de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


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
            f"❌ ERRO: Arquivo 'youtube_links.txt' não encontrado na pasta 'backend'. Crie este arquivo com os links dos vídeos.")
        return

    with open(LINKS_FILE, 'r') as f:
        urls = [line.strip() for line in f if line.strip().startswith("http")]

    print(f"\nINFO: Encontrados {len(urls)} links no arquivo '{LINKS_FILE.name}'.")

    for url in urls:
        try:
            yt = YouTube(url)
            # Cria um nome de arquivo seguro a partir do título para evitar erros
            safe_title = sanitize_filename(yt.title)
            # Usa o ID do vídeo para garantir um nome de arquivo único
            json_name = f"youtube_{yt.video_id}_{safe_title[:50]}.json"
            json_path = DATA_DIR / json_name

            if json_path.exists():
                print(f"⏭️  Pulando '{yt.title}', transcrição já existe.")
                continue

            print(f"\n baixando áudio de: '{yt.title}'...")
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
                    "video_name": url
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
    transcribe_youtube_videos()