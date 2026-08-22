# Use Python 3.11 slim image for production
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOST=0.0.0.0 \
    INDEX_DIR=index/semantic_multilingual

WORKDIR /app

# Install only CPU-compatible runtime dependencies. This avoids the large CUDA/NVIDIA
# packages that PyTorch may otherwise install in a generic Linux image.
COPY requirements-railway.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-railway.txt

# Copy application source code, web frontend, and pre-built vector index
COPY src/ ./src/
COPY web/ ./web/
COPY index/semantic_multilingual/ ./index/semantic_multilingual/
COPY main.py .

# Start the unified web & RAG service
CMD ["python", "main.py"]
