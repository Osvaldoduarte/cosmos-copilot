# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-backend.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copy application code
COPY . .

# Expose port (Cloud Run will set PORT env var)
ENV PORT=8080

# Run the application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}