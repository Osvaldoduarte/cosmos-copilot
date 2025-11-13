# Use a imagem slim do Python 3.11
FROM python:3.11-slim
WORKDIR /app

# 1. Instala 'curl' + ferramentas de build
RUN apt-get update && \
    apt-get install -y git build-essential python3-dev curl && \
    rm -rf /var/lib/apt/lists/*

# 2. Copia e instala as dependências.
COPY requirements-backend.txt .
RUN pip install -r requirements-backend.txt

# 💡 CORREÇÃO:
# Em vez de 'curl', usamos o Python para pré-baixar o modelo.
# Isso força a biblioteca de IA a fazer o download durante o build.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# 4. Copia o código-fonte restante
COPY . .

# 5. Roda o servidor
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]