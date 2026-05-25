# ollama-rag-api

**Chat with your local documents using a local LLM. Nothing leaves your machine.**

A small, self-hosted RAG stack: drop documents into a folder, embed them into
Chroma, and query them through a Flask REST API powered by an Ollama-served LLM.
Ships with an interactive Swagger UI, a Streamlit chat frontend, ready-to-run
client examples, a Postman collection, and a Docker setup that runs the whole
thing in one container.

---

## Architecture

```
                            ┌────────────────────┐
  Streamlit chat UI ─┐      │  LangChain         │      ┌──► Chroma vectorstore
                     ├─►  Flask  ──► RetrievalQA  ──┤
  curl / Postman /  ─┘     /ask                    │      └──► Ollama LLM
  python_client.py         /health
                           /apidocs  (Swagger UI)
```

---

## Quick start (local)

Prereqs: Python 3.11+, [Ollama](https://ollama.com) installed and running
(`ollama serve` or the menu-bar app).

```bash
make install      # python -m venv .venv && pip install -r requirements.txt
make ollama       # ollama pull llama3.2   (skip if you already have a model)
# drop your docs into source_documents/  (a demo test.pdf ships in the repo)
make ingest       # embed everything into db/
make run          # API on :5001, Streamlit UI on :8501
```

Open:

- **Streamlit chat UI** — http://localhost:8501
- **Swagger UI** — http://localhost:5001/apidocs
- **Health probe** — http://localhost:5001/health

`make help` lists every target.

---

## Quick start (Docker)

```bash
make docker       # builds the image, then runs it with 5001 / 8501 / 11434 exposed
```

The container runs Ollama, pulls the model lazily if missing, ingests
`source_documents/` only when it has content and no `db/` exists, then serves
the API and Streamlit. Mount your own `source_documents/` and `db/` as volumes
(the Makefile does this for you).

---

## API reference

### `GET /health`

Liveness probe. Returns the configured model name.

```bash
$ curl -s http://localhost:5001/health
{"status":"ok","model":"llama3.2"}
```

### `POST /ask`

Run a RAG query over the ingested documents.

**Request**

| field | type   | required | description                        |
|-------|--------|----------|------------------------------------|
| query | string | yes      | The natural-language question      |

**Response**

| field        | type   | description                                              |
|--------------|--------|----------------------------------------------------------|
| query        | string | Echo of the request query                                |
| answer       | string | LLM answer grounded in the retrieved chunks              |
| time_taken   | number | Seconds spent on retrieval + generation                  |
| documents    | array  | The source chunks used; each has `source` and `content`  |

**Status codes:** `200` ok · `400` missing query · `500` internal error.

**Examples**

```bash
# curl
curl -X POST http://localhost:5001/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is this document about?"}'

# httpie
http POST :5001/ask query="What is this document about?"

# python
python examples/python_client.py "What is this document about?"
```

Interactive playground with "Try it out": **http://localhost:5001/apidocs**.
The raw OpenAPI spec is at `/apispec_1.json`.

Postman: import `examples/postman_collection.json`, set the `API_URL`
variable, and hit either request.

---

## Streamlit UI

A small chat frontend at http://localhost:8501. Sidebar shows live API health
and links straight to Swagger. Each assistant turn has an expandable
**Sources** section listing the retrieved chunks so you can verify the
answer is grounded.

Reads `API_URL` from the env (defaults to `http://localhost:5001`), so it
points at either the local Flask process or a Dockerised API.

---

## Configuration

All values are env vars; defaults are sensible. See `.env.example`.

| variable                | default              | purpose                                     |
|-------------------------|----------------------|---------------------------------------------|
| `MODEL`                 | `llama3.2`           | Ollama model name                           |
| `EMBEDDINGS_MODEL_NAME` | `all-MiniLM-L6-v2`   | HuggingFace sentence-transformers model     |
| `PERSIST_DIRECTORY`     | `db`                 | Where Chroma persists the vector store      |
| `TARGET_SOURCE_CHUNKS`  | `4`                  | Chunks retrieved per query                  |
| `PORT`                  | `5001`               | Port the Flask API binds to                 |
| `API_URL`               | `http://localhost:5001` | Where the UI/examples reach the API     |
| `FLASK_DEBUG`           | `0`                  | `1` enables Flask debug — **never in prod** |

---

## Supported document types

`.csv`, `.doc`, `.docx`, `.enex`, `.eml`, `.epub`, `.html`, `.md`, `.odt`,
`.pdf`, `.ppt`, `.pptx`, `.txt`.

Drop files into `source_documents/` and run `make ingest`. Re-running adds
only new files; the existing vector store is preserved.

---

## Examples

Everything lives under `examples/`:

- `curl.sh` — single-shot curl POST to `/ask`, JSON-safe quoting + jq
- `httpie.sh` — same in HTTPie syntax
- `python_client.py` — minimal `ChatClient` with `health()` and `ask()`
- `postman_collection.json` — Postman v2.1 collection (importable)

---

## Troubleshooting

- **`/health` returns `500` / connection refused** — Ollama isn't running.
  Run `ollama serve` in another terminal (the Docker setup handles this for you).
- **Port already in use** — override with `PORT=5050 make api` (Flask) or
  `make ui -- --server.port 8600` (Streamlit). Default ports: `5001` (API),
  `8501` (UI), `11434` (Ollama).
- **macOS `Address already in use` on 5000** — that's why the API defaults
  to `5001`. macOS Monterey+ binds port 5000 for AirPlay Receiver. You can
  either keep `5001` (recommended) or disable AirPlay Receiver in
  *System Settings → General → AirDrop & Handoff*.
- **Ingest reports "No new documents to load"** — the file is already in the
  store. To re-ingest from scratch: `make clean && make ingest`.
- **First model pull is slow** — `llama3.2` is ~2 GB. Switch to a different
  model via `MODEL=mistral make ollama && MODEL=mistral make api`.

---

## Credits

- Originally inspired by [imartinez/privateGPT](https://github.com/imartinez/privateGPT) — the CLI design and ingest pipeline trace back to that project.
- LLM serving via [Ollama](https://ollama.com).
- Embeddings via [sentence-transformers](https://www.sbert.net/).
- Vector store via [Chroma](https://www.trychroma.com/).

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
