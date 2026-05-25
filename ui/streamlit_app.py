import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:5001")

st.set_page_config(page_title="ollama-rag-api", page_icon="💬", layout="wide")
st.title("💬 Chat with your documents")
st.caption("RAG over local docs via Ollama. Nothing leaves your machine.")

with st.sidebar:
    st.header("API")
    try:
        h = requests.get(f"{API_URL}/health", timeout=3).json()
        st.success(f"✅ Up — model: `{h.get('model','?')}`")
    except Exception as e:
        st.error(f"❌ Unreachable at {API_URL}\n\n{e}")
    st.markdown(f"- [Swagger UI]({API_URL}/apidocs)")
    st.markdown(f"- [Raw spec]({API_URL}/apispec_1.json)")
    st.divider()
    st.caption(f"API_URL = `{API_URL}`")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("documents"):
            with st.expander(f"📚 Sources ({len(msg['documents'])})"):
                for d in msg["documents"]:
                    st.markdown(f"**{d['source']}**")
                    st.code(d["content"][:500] + ("…" if len(d["content"]) > 500 else ""))

if prompt := st.chat_input("Ask a question about your documents"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                r = requests.post(f"{API_URL}/ask", json={"query": prompt}, timeout=300)
                r.raise_for_status()
                data = r.json()
                answer = data.get("answer", "(no answer)")
                docs = data.get("documents", [])
                st.markdown(answer)
                if docs:
                    with st.expander(f"📚 Sources ({len(docs)})"):
                        for d in docs:
                            st.markdown(f"**{d['source']}**")
                            st.code(d["content"][:500] + ("…" if len(d["content"]) > 500 else ""))
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "documents": docs}
                )
            except Exception as e:
                err = f"Request failed: {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})
