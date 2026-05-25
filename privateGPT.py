from flask import Flask, request, jsonify
from langchain.chains import RetrievalQA
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
from langchain.llms import Ollama
import os
import time

app = Flask(__name__)

# Configuration for LLM and embeddings
model = os.getenv("MODEL", "llama3")
embeddings_model_name = os.getenv("EMBEDDINGS_MODEL_NAME", "all-MiniLM-L6-v2")
persist_directory = os.getenv("PERSIST_DIRECTORY", "db")
target_source_chunks = int(os.getenv('TARGET_SOURCE_CHUNKS', 4))

embeddings = HuggingFaceEmbeddings(model_name=embeddings_model_name)
db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
retriever = db.as_retriever(search_kwargs={"k": target_source_chunks})
llm = Ollama(model=model)
qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever, return_source_documents=True)

@app.route('/ask', methods=['POST'])
def ask_question():
    try:
        data = request.json
        query = data.get('query')
        if not query:
            print('Error: No query provided')
            return jsonify({'error': 'No query provided'}), 400

        print('Processing query:', query)
        start = time.time()
        res = qa(query)
        answer, docs = res['result'], res['source_documents']
        end = time.time()

        print('Query processed in', end - start, 'seconds')
        response = {
            'query': query,
            'answer': answer,
            'time_taken': end - start,
            'documents': [{'source': doc.metadata["source"], 'content': doc.page_content} for doc in docs]
        }
        return jsonify(response)
    except Exception as e:
        print('Failed to process query:', str(e))
        return jsonify({'error': 'Failed to process the request', 'details': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)




# request to flask
# request to LLM
# response from LLM/Postman
