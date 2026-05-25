# Multi-arch base (works on linux/amd64 and linux/arm64).
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# System deps:
#   curl       — fetch the Ollama install script + health-poll the daemon
#   ca-certs   — TLS to huggingface, ollama, etc.
#   git        — some Python packages still need it
#   build-ess. — wheels that lack ARM/x86 prebuilt binaries
#   zstd       — required by the Ollama installer's tarball extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        git \
        build-essential \
        zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama (the script is multi-arch and idempotent).
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

# Install Python deps first so iterating on code doesn't bust the layer cache.
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

# Copy the rest of the project. .dockerignore keeps db/, .venv, .git, etc. out.
COPY . /app

RUN chmod +x /app/pull-model.sh /app/docker-entrypoint.sh

# Ollama (11434), Flask API (5000), Streamlit UI (8501)
EXPOSE 11434 5000 8501

CMD ["/app/docker-entrypoint.sh"]
