import os
import time
from pathlib import Path

from flask import Flask, jsonify, request
from flasgger import Swagger
from werkzeug.utils import secure_filename

from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.llms import Ollama
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Chroma

from ingest import load_single_document  # reuse loader registry

app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "ollama-rag-api",
        "description": "Chat with your local documents using a local LLM via Ollama. "
                       "No data leaves your machine.",
        "version": "1.1.0",
    },
    "schemes": ["http"],
})

model = os.getenv("MODEL", "llama3.2")
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "all-MiniLM-L6-v2")
persist_directory = os.getenv("PERSIST_DIRECTORY", "db")
source_directory = os.getenv("SOURCE_DIRECTORY", "source_documents")
target_source_chunks = int(os.getenv("TARGET_SOURCE_CHUNKS", 4))

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
SUMMARIZE_CHAR_LIMIT = 16000  # cap on text fed to the LLM for a summary

embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})
llm = Ollama(model=model)
qa = RetrievalQA.from_chain_type(
    llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True
)


# --------------------------- helpers ---------------------------

def _safe_source_path(filename: str) -> Path:
    """Resolve a user-supplied filename inside source_directory, blocking path traversal."""
    safe = secure_filename(filename)
    if not safe:
        raise ValueError("Invalid filename")
    return (Path(source_directory) / safe).resolve()


def _all_metadatas():
    try:
        data = db.get(include=["metadatas"])
        return data.get("metadatas") or [], data.get("ids") or []
    except Exception:
        return [], []


def _persist():
    try:
        db.persist()
    except Exception:
        # Chroma 0.4+ auto-persists; older paths may still need this.
        pass


def _dedupe_docs(docs):
    seen, unique = set(), []
    for doc in docs:
        key = (doc.metadata.get("source", ""), doc.page_content)
        if key in seen:
            continue
        seen.add(key)
        unique.append({"source": key[0], "content": key[1]})
    return unique


# --------------------------- meta ---------------------------

@app.route("/health", methods=["GET"])
def health():
    """Liveness probe.
    ---
    tags: [meta]
    responses:
      200:
        description: API is up and the configured model name
        schema:
          type: object
          properties:
            status: { type: string, example: ok }
            model:  { type: string, example: llama3.2 }
    """
    return jsonify({"status": "ok", "model": model})


# --------------------------- chat modes ---------------------------

@app.route("/ask", methods=["POST"])
def ask_question():
    """RAG-style question: retrieves chunks then asks the LLM for an answer.
    ---
    tags: [chat]
    consumes: [application/json]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [query]
          properties:
            query: { type: string, example: What is this document about? }
    responses:
      200:
        description: Answer plus the deduped source chunks used to produce it
        schema:
          type: object
          properties:
            query:      { type: string }
            answer:     { type: string }
            time_taken: { type: number, format: float }
            documents:
              type: array
              items:
                type: object
                properties:
                  source:  { type: string }
                  content: { type: string }
      400: { description: Missing or empty query }
      500: { description: Internal error while processing the query }
    """
    try:
        data = request.json or {}
        query = data.get("query")
        if not query:
            return jsonify({"error": "No query provided"}), 400

        start = time.time()
        res = qa(query)
        end = time.time()
        return jsonify({
            "query": query,
            "answer": res["result"],
            "time_taken": end - start,
            "documents": _dedupe_docs(res["source_documents"]),
        })
    except Exception as e:
        return jsonify({"error": "Failed to process the request", "details": str(e)}), 500


@app.route("/chat", methods=["POST"])
def chat():
    """Talk to the LLM directly with no retrieval.
    ---
    tags: [chat]
    consumes: [application/json]
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [query]
          properties:
            query: { type: string, example: Explain RAG in one sentence. }
    responses:
      200:
        description: Model answer (no source documents)
        schema:
          type: object
          properties:
            query:      { type: string }
            answer:     { type: string }
            time_taken: { type: number, format: float }
      400: { description: Missing or empty query }
      500: { description: Internal error while calling the LLM }
    """
    try:
        data = request.json or {}
        query = data.get("query")
        if not query:
            return jsonify({"error": "No query provided"}), 400
        start = time.time()
        answer = llm(query)
        end = time.time()
        return jsonify({"query": query, "answer": answer, "time_taken": end - start})
    except Exception as e:
        return jsonify({"error": "Failed to process the request", "details": str(e)}), 500


@app.route("/summarize", methods=["POST"])
def summarize():
    """Summarize one specific ingested file, or the whole corpus if no file is given.
    ---
    tags: [chat]
    consumes: [application/json]
    parameters:
      - in: body
        name: body
        required: false
        schema:
          type: object
          properties:
            file:
              type: string
              description: Filename (basename) of an ingested file. Omit to summarize everything.
              example: test.pdf
    responses:
      200:
        description: Summary plus metadata about what was summarized
        schema:
          type: object
          properties:
            file:        { type: string, description: "'all' or the requested filename" }
            answer:      { type: string }
            chunks_used: { type: integer }
            truncated:   { type: boolean, description: True if the corpus was clipped to fit the LLM context }
            time_taken:  { type: number, format: float }
      404: { description: No matching content in the vectorstore }
      500: { description: Internal error }
    """
    try:
        data = request.json or {}
        target = data.get("file")
        start = time.time()

        metadatas, ids = _all_metadatas()
        if not metadatas:
            return jsonify({"error": "No ingested content"}), 404

        get_kwargs = {"include": ["documents", "metadatas"]}
        result = db.get(**get_kwargs)
        contents = result.get("documents") or []
        metas = result.get("metadatas") or []

        if target:
            filtered = [
                c for c, m in zip(contents, metas)
                if os.path.basename(m.get("source", "")) == target
            ]
            if not filtered:
                return jsonify({"error": f"No chunks found for file '{target}'"}), 404
            contents = filtered

        full_text = "\n\n".join(contents)
        truncated = len(full_text) > SUMMARIZE_CHAR_LIMIT
        if truncated:
            full_text = full_text[:SUMMARIZE_CHAR_LIMIT] + "\n\n[... truncated ...]"

        prompt = (
            "Summarize the following document content concisely. "
            "Capture the main points and any key facts.\n\n"
            f"---\n{full_text}\n---\n\nSummary:"
        )
        answer = llm(prompt)
        end = time.time()

        return jsonify({
            "file": target or "all",
            "answer": answer,
            "chunks_used": len(contents),
            "truncated": truncated,
            "time_taken": end - start,
        })
    except Exception as e:
        return jsonify({"error": "Failed to summarize", "details": str(e)}), 500


# --------------------------- file management ---------------------------

@app.route("/files", methods=["GET"])
def list_files():
    """List files in source_documents/ with per-file chunk counts from the vectorstore.
    ---
    tags: [files]
    responses:
      200:
        description: Files currently in the corpus
        schema:
          type: object
          properties:
            files:
              type: array
              items:
                type: object
                properties:
                  name:       { type: string, example: test.pdf }
                  size_bytes: { type: integer, example: 141013 }
                  chunks:     { type: integer, description: Number of chunks in the vectorstore }
    """
    src = Path(source_directory)
    if not src.exists():
        return jsonify({"files": []})

    chunk_counts = {}
    for meta in _all_metadatas()[0]:
        base = os.path.basename(meta.get("source", ""))
        chunk_counts[base] = chunk_counts.get(base, 0) + 1

    files = []
    for entry in sorted(src.iterdir()):
        if not entry.is_file() or entry.name.startswith("."):
            continue
        files.append({
            "name": entry.name,
            "size_bytes": entry.stat().st_size,
            "chunks": chunk_counts.get(entry.name, 0),
        })
    return jsonify({"files": files})


@app.route("/ingest", methods=["POST"])
def ingest_file():
    """Upload a file (multipart form, field name 'file') and ingest it into the vectorstore.
    ---
    tags: [files]
    consumes: [multipart/form-data]
    parameters:
      - in: formData
        name: file
        type: file
        required: true
        description: Document to ingest. Supported types match ingest.py's loader registry.
    responses:
      200:
        description: File saved and chunked into the vectorstore
        schema:
          type: object
          properties:
            file:          { type: string }
            chunks_added:  { type: integer }
            time_taken:    { type: number, format: float }
      400: { description: Missing file or unsupported extension }
      500: { description: Failed to load or embed the file }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (multipart field name must be 'file')"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    try:
        dest = _safe_source_path(f.filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    dest.parent.mkdir(parents=True, exist_ok=True)
    f.save(dest)

    try:
        start = time.time()
        docs = load_single_document(str(dest))
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        chunks = splitter.split_documents(docs)
        if chunks:
            db.add_documents(chunks)
            _persist()
        end = time.time()
        return jsonify({
            "file": dest.name,
            "chunks_added": len(chunks),
            "time_taken": end - start,
        })
    except Exception as e:
        # Roll back the saved file so a failed ingest doesn't leave orphans
        try:
            dest.unlink(missing_ok=True)
        except Exception:
            pass
        return jsonify({"error": "Ingest failed", "details": str(e)}), 500


@app.route("/files/<path:filename>", methods=["DELETE"])
def delete_file(filename):
    """Remove a file from source_documents/ and delete its chunks from the vectorstore.
    ---
    tags: [files]
    parameters:
      - in: path
        name: filename
        type: string
        required: true
        description: Basename of the file to delete (e.g. test.pdf)
    responses:
      200:
        description: File and its chunks removed
        schema:
          type: object
          properties:
            deleted:         { type: string }
            chunks_removed:  { type: integer }
            file_removed:    { type: boolean }
      400: { description: Invalid filename }
    """
    try:
        target = _safe_source_path(filename)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    chunks_removed = 0
    metadatas, ids = _all_metadatas()
    ids_to_drop = [
        i for i, m in zip(ids, metadatas)
        if os.path.basename(m.get("source", "")) == target.name
    ]
    if ids_to_drop:
        try:
            db.delete(ids=ids_to_drop)
            _persist()
            chunks_removed = len(ids_to_drop)
        except Exception as e:
            return jsonify({"error": "Failed to delete chunks", "details": str(e)}), 500

    file_removed = False
    if target.exists():
        target.unlink()
        file_removed = True

    return jsonify({
        "deleted": target.name,
        "chunks_removed": chunks_removed,
        "file_removed": file_removed,
    })


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    port = int(os.getenv("PORT", "5001"))
    app.run(debug=debug, host="0.0.0.0", port=port)
