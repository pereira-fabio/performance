FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application and the operator scripts that the README and
# docs tell you to run with `docker exec ... python backend/<script>.py`.
COPY app/ ./backend/app/
COPY backup.py ./backend/backup.py
COPY dem_tiles.py ./backend/dem_tiles.py
COPY seed_demo_data.py ./backend/seed_demo_data.py

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DATA_DIR=/data
ENV DATABASE_URL=sqlite:////data/peakpace.db

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
