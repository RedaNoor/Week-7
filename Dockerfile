FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by psycopg2, numpy, scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY . /app

# PYTHONPATH so `from app.xxx import ...` works from inside /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000

# Use $PORT env var so Railway can inject its own port; default to 8000 locally
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]