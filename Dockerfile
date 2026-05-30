FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY frontend/package*.json frontend/
RUN cd frontend && npm install

COPY . .
RUN cd frontend && npm run build

WORKDIR /app/backend
CMD ["python", "start_server.py"]
