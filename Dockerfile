FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Preserve the same backend/app + frontend relative layout as local dev,
# so app/main.py's FRONTEND_DIR path resolution (parent.parent.parent / "frontend")
# resolves identically in both environments.
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY frontend ./frontend

RUN mkdir -p /app/data

ENV DATABASE_URL=sqlite:////app/data/finora.db
ENV PYTHONUNBUFFERED=1

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
