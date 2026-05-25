#!/bin/bash
# Container entrypoint:
#   1. Start Ollama daemon
#   2. Pull the configured model (if missing)
#   3. Ingest source_documents/ if non-empty and no db/ yet
#   4. Launch the Flask API on :5001 and Streamlit on :8501
set -euo pipefail

MODEL="${MODEL:-llama3.2}"

ollama serve &
OLLAMA_PID=$!

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! ollama list | awk '{print $1}' | grep -qx "$MODEL"; then
  ollama pull "$MODEL"
fi

if [ -n "$(ls -A /app/source_documents 2>/dev/null | grep -v '^\.gitkeep$' || true)" ] \
   && [ ! -d /app/db ]; then
  echo "[entrypoint] ingesting source_documents/ into Chroma db/"
  python3 /app/ingest.py
else
  echo "[entrypoint] skipping ingest (no source documents or db/ already exists)"
fi

python3 /app/api.py &
API_PID=$!

streamlit run /app/ui/streamlit_app.py \
  --server.port 8501 --server.address 0.0.0.0 &
UI_PID=$!

trap 'kill $OLLAMA_PID $API_PID $UI_PID 2>/dev/null || true' EXIT INT TERM
wait -n $OLLAMA_PID $API_PID $UI_PID
