FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY frontend/ /app/frontend/
COPY tabelas/ /app/tabelas/

# Usuário não-root
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
