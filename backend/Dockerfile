# Use a imagem slim do Python 3.11
FROM python:3.11-slim
WORKDIR /app

# --- CORREÇÃO ---
# Instala git E as ferramentas de build (build-essential, python3-dev)
# necessárias para compilar dependências como bcrypt.
RUN apt-get update && \
    apt-get install -y git build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copia e instala as dependências.
COPY requirements-backend.txt .
RUN pip install -r requirements-backend.txt

# Copia o código-fonte restante
COPY . .

# O Cloud Run espera que o app rode na porta 8080 por padrão
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]