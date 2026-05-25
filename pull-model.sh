#!/bin/bash
# Pull the configured LLM into the local Ollama instance.
# Honours the MODEL env var (default: llama3).
#
# On a host with Ollama already running, just `ollama pull` is enough.
# Inside the container we have to start `ollama serve` first.
set -euo pipefail

MODEL="${MODEL:-llama3}"

if pgrep -x ollama >/dev/null 2>&1; then
  ollama pull "$MODEL"
  exit 0
fi

ollama serve &
SERVICE_PID=$!
trap 'kill $SERVICE_PID 2>/dev/null || true; wait $SERVICE_PID 2>/dev/null || true' EXIT

# Wait for the daemon socket instead of a fixed sleep.
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

ollama pull "$MODEL"
