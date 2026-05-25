# ollama-rag-api

**Chat with your local documents using a local LLM. Nothing leaves your machine.**

A small, self-hosted RAG stack: drop documents into a folder, embed them into
Chroma, and query them through a Flask REST API powered by an Ollama-served LLM.
The API supports four chat modes (RAG, direct chat, search-only, summarize) and
full file management (upload, list, delete) so the Streamlit frontend, curl,
Postman, or any custom client can drive the whole experience without touching
the filesystem. Ships with an interactive Swagger UI and a Docker setup that
runs the whole stack in one container.

---

## Architecture

```
                                     ┌──► Chroma vectorstore
  Streamlit chat UI ─┐        Flask  │
                     ├─► /ask, /chat, /summarize  ──► LangChain ──┤
  curl / Postman /  ─┘    /files (GET/POST/DELETE)                │
  python_client.py        /health, /apidocs                       └──► Ollama LLM
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

Eight endpoints across three groups. Interactive playground with "Try it out"
is at **http://localhost:5001/apidocs**; the raw OpenAPI spec lives at
`/apispec_1.json`. The full request/response shapes are also captured in
`examples/postman_collection.json`.

| method | path                  | purpose                                              |
|--------|-----------------------|------------------------------------------------------|
| GET    | `/health`             | Liveness probe                                       |
| POST   | `/ask`                | RAG: retrieve + answer with sources                  |
| POST   | `/chat`               | Talk to the LLM directly, no retrieval               |
| POST   | `/summarize`          | Summarize one file or the whole corpus               |
| GET    | `/files`              | List ingested files + per-file chunk counts          |
| POST   | `/ingest`             | Upload a file (multipart) and add it to the corpus   |
| DELETE | `/files/<name>`       | Remove a file and its chunks from the vectorstore    |

### Meta

#### `GET /health`

```bash
$ curl -s http://localhost:5001/health
{"status":"ok","model":"llama3.2"}
```

### Chat modes

#### `POST /ask`  — RAG

Retrieves the top-`TARGET_SOURCE_CHUNKS` chunks and asks the LLM for a grounded answer.

```bash
curl -X POST http://localhost:5001/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is this document about?"}'
```

Returns `{query, answer, time_taken, documents: [{source, content}]}`. Duplicate
chunks are removed; only unique `(source, content)` pairs are returned.

#### `POST /chat`  — no retrieval

```bash
curl -X POST http://localhost:5001/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"Explain RAG in one sentence."}'
```

Returns `{query, answer, time_taken}`. Faster than `/ask` (skips embedding +
similarity search).

#### `POST /summarize`  — whole-doc summary

```bash
# one file
curl -X POST http://localhost:5001/summarize \
  -H 'Content-Type: application/json' \
  -d '{"file":"test.pdf"}'

# everything
curl -X POST http://localhost:5001/summarize \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Returns `{file, answer, chunks_used, truncated, time_taken}`. Concatenated
chunks are clipped at 16 000 chars before being sent to the LLM (the `truncated`
flag tells you when that happened).

### File management

#### `GET /files`

```bash
$ curl -s http://localhost:5001/files
{"files":[{"name":"test.pdf","size_bytes":141013,"chunks":6}]}
```

#### `POST /ingest`  — multipart upload

```bash
curl -X POST http://localhost:5001/ingest \
  -F 'file=@/path/to/your-doc.pdf'
```

Returns `{file, chunks_added, time_taken}`. Supported types match the list in
[Supported document types](#supported-document-types). The file is rolled back
from disk if embedding fails, so a failed upload leaves no orphans.

#### `DELETE /files/<name>`

```bash
curl -X DELETE http://localhost:5001/files/test.pdf
```

Returns `{deleted, chunks_removed, file_removed}`. Removes both the file from
`source_documents/` and its chunks from Chroma (filtered by `metadata.source` —
no full re-ingest needed).

### Other clients

```bash
http POST :5001/ask query="What is this document about?"   # httpie
python examples/python_client.py "What is this document about?"
```

Postman: import `examples/postman_collection.json`, set the `API_URL`
variable, and hit any request.

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
