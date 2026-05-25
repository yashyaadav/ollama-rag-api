.PHONY: help install ollama ingest api ui run docker docker-build docker-run clean

PY      := .venv/bin/python
PIP     := .venv/bin/pip
STREAM  := .venv/bin/streamlit
MODEL   ?= llama3.2
IMAGE   ?= ollama-rag-api

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Create .venv and install Python deps
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

ollama:  ## Pull the LLM into the local Ollama instance
	./pull-model.sh

ingest:  ## Embed everything under source_documents/ into Chroma (db/)
	$(PY) ingest.py

api:  ## Run the Flask API on :5000 (Swagger UI at /apidocs)
	$(PY) api.py

ui:  ## Run the Streamlit chat UI on :8501
	$(STREAM) run ui/streamlit_app.py

run:  ## Run API in the background and Streamlit in the foreground
	$(PY) api.py & echo $$! > .api.pid; \
	trap 'kill $$(cat .api.pid) 2>/dev/null; rm -f .api.pid' EXIT INT TERM; \
	sleep 2; \
	$(STREAM) run ui/streamlit_app.py

docker-build:  ## Build the Docker image
	docker build -t $(IMAGE) .

docker-run:  ## Run the Docker image with API + UI + Ollama exposed
	docker run --rm -p 5000:5000 -p 8501:8501 -p 11434:11434 \
	  -v $$PWD/source_documents:/app/source_documents \
	  -v $$PWD/db:/app/db \
	  $(IMAGE)

docker: docker-build docker-run  ## Build then run

clean:  ## Remove vector store, logs, and bytecode caches
	rm -rf db/ logs/ __pycache__/ */__pycache__/
