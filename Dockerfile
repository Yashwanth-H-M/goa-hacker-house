# Use Python 3.11 slim image for production
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    INDEX_DIR=index/semantic_multilingual

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code, web frontend, and pre-built vector index
COPY src/ ./src/
COPY web/ ./web/
COPY index/semantic_multilingual/ ./index/semantic_multilingual/
COPY main.py .

# Start the unified web & RAG service
CMD ["python", "main.py"]
