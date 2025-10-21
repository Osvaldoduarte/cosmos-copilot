FROM python:3.9-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expõe a porta 8000
EXPOSE 8000

# Comando para iniciar o servidor ChromaDB usando o Postgres como backend
# Ele vai ler as variáveis de ambiente (PG_HOST, etc.)
CMD ["chroma", "run", "--path", "/app/chroma-data", "--host", "0.0.0.0", "--port", "8000", "--backend", "pg"]