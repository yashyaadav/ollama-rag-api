from flask import Flask, request, jsonify
from flasgger import Swagger
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import Ollama
import os
import time

app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "ollama-rag-api",
        "description": "Chat with your local documents using a local LLM via Ollama. "
                       "No data leaves your machine.",
        "version": "1.0.0",
    },
    "schemes": ["http"],
})

model = os.getenv("MODEL", "llama3")
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "all-MiniLM-L6-v2")
persist_directory = os.getenv("PERSIST_DIRECTORY", "db")
target_source_chunks = int(os.getenv("TARGET_SOURCE_CHUNKS", 4))

embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})
llm = Ollama(model=model)
qa = RetrievalQA.from_chain_type(
    llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True
)


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe.
    ---
    tags:
      - meta
    responses:
      200:
        description: API is up and the configured model name
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            model:
              type: string
              example: llama3
    """
    return jsonify({"status": "ok", "model": model})


@app.route("/ask", methods=["POST"])
def ask_question():
    """Ask a question over the ingested documents.
    ---
    tags:
      - rag
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [query]
          properties:
            query:
              type: string
              example: What is this document about?
    responses:
      200:
        description: Answer plus the source document chunks used to produce it
        schema:
          type: object
          properties:
            query:
              type: string
            answer:
              type: string
            time_taken:
              type: number
              format: float
            documents:
              type: array
              items:
                type: object
                properties:
                  source:
                    type: string
                  content:
                    type: string
      400:
        description: Missing or empty query
      500:
        description: Internal error while processing the query
    """
    try:
        data = request.json
        query = data.get("query")
        if not query:
            print("Error: No query provided")
            return jsonify({"error": "No query provided"}), 400

        print("Processing query:", query)
        start = time.time()
        res = qa(query)
        answer, docs = res["result"], res["source_documents"]
        end = time.time()

        print("Query processed in", end - start, "seconds")
        response = {
            "query": query,
            "answer": answer,
            "time_taken": end - start,
            "documents": [
                {"source": doc.metadata["source"], "content": doc.page_content}
                for doc in docs
            ],
        }
        return jsonify(response)
    except Exception as e:
        print("Failed to process query:", str(e))
        return jsonify({"error": "Failed to process the request", "details": str(e)}), 500


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=5000)
