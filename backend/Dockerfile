# AEGIS backend. The Playwright image ships Chromium matching playwright==1.63.0.
FROM mcr.microsoft.com/playwright/python:v1.63.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY aegis ./aegis

ENV DATA_DIR=/data \
    DATABASE_URL=sqlite+aiosqlite:////data/aegis.db \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000

# One process: the job queue runs inside it, so do not add uvicorn workers.
CMD ["uvicorn", "aegis.main:app", "--host", "0.0.0.0", "--port", "8000"]
