FROM python:3.9-slim
WORKDIR /app

# Copia primeiro o requirements para aproveitar o cache do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Agora copia o resto do código do backend
COPY . .

# O Cloud Run injeta a variável PORT, mas 8080 é um padrão seguro
EXPOSE 8080

# Comando para iniciar sua aplicação FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]