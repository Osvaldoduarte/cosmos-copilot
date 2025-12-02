import os
import base64
import httpx
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
import google.generativeai as genai
from core.shared import print_error, print_info, print_success

class MediaService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
            print_error("❌ GEMINI_API_KEY not found for MediaService")

    async def process_media(self, message_id: str, instance_name: str, evolution_url: str, evolution_key: str, media_type: str) -> str:
        """
        Baixa a mídia da Evolution API e usa o Gemini para transcrever (áudio/vídeo) ou descrever (imagem).
        Retorna o texto gerado.
        """
        if not self.model:
            return None

        print_info(f"🎬 Iniciando processamento de mídia: {message_id} ({media_type})")

        # 1. Download Media via Evolution API (getBase64)
        url = f"{evolution_url}/chat/getBase64FromMediaMessage/{instance_name}"
        payload = {
            "message": { "key": { "id": message_id } },
            "convertToMp4": False
        }
        headers = {"apikey": evolution_key, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, headers=headers, json=payload, timeout=60.0)
                if resp.status_code != 200:
                    print_error(f"❌ Falha ao baixar mídia {message_id}: {resp.text}")
                    return None
                
                data = resp.json()
                base64_str = data.get("base64")
                mimetype = data.get("mimetype")
                
                if not base64_str:
                    print_error(f"❌ Base64 vazio para mídia {message_id}")
                    return None

                # 2. Salva em Arquivo Temporário (Executa em thread para não bloquear loop)
                loop = asyncio.get_running_loop()
                text_result = await loop.run_in_executor(
                    None, 
                    self._upload_and_generate, 
                    base64_str, mimetype, media_type
                )
                
                return text_result

        except Exception as e:
            print_error(f"❌ Erro no processamento de mídia: {e}")
            return None

    def _upload_and_generate(self, base64_str, mimetype, media_type):
        try:
            # Decodifica
            file_bytes = base64.b64decode(base64_str)
            suffix = "." + mimetype.split("/")[-1] if mimetype else ".bin"
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                # Upload para Gemini
                print_info(f"📤 Uploading para Gemini...")
                uploaded_file = genai.upload_file(tmp_path, mime_type=mimetype)
                
                # Prompt adequado
                if "audio" in media_type.lower():
                    prompt = "Transcreva este áudio fielmente. Se houver falas, escreva-as. Se for apenas som, descreva."
                elif "image" in media_type.lower():
                    prompt = "Descreva esta imagem detalhadamente para que um vendedor possa entender o contexto."
                elif "video" in media_type.lower():
                    prompt = "Transcreva o áudio deste vídeo e descreva visualmente o que acontece de importante."
                else:
                    prompt = "Descreva o conteúdo deste arquivo."

                # Gera Conteúdo
                print_info(f"🧠 Gemini processando...")
                result = self.model.generate_content([uploaded_file, prompt])
                text = result.text.strip()
                
                print_success(f"✅ Mídia processada: {text[:50]}...")
                return text

            finally:
                # Limpeza
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                # Opcional: genai.delete_file(uploaded_file.name)
        except Exception as e:
            print_error(f"❌ Erro interno Gemini: {e}")
            return None

media_service = MediaService()
