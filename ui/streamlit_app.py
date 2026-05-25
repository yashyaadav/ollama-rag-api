import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:5001")

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / os.getenv("SOURCE_DIRECTORY", "source_documents")
PERSIST_DIR = REPO_ROOT / os.getenv("PERSIST_DIRECTORY", "db")

SUPPORTED_EXTS = [
    "pdf", "txt", "md", "docx", "doc", "csv",
    "html", "pptx", "ppt", "epub", "odt", "eml", "enex", "msg",
]

st.set_page_config(page_title="ollama-rag-api", page_icon="🦙", layout="wide")

st.markdown(
    """
<style>
  .ora-banner {
    background: linear-gradient(90deg, #d4c8f7 0%, #c5b5f7 100%);
    padding: 22px;
    border-radius: 10px;
    margin-bottom: 20px;
    text-align: center;
  }
  .ora-banner h1 {
    color: #1a1a2e;
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    font-weight: 700;
    letter-spacing: 4px;
    margin: 0;
    font-size: 26px;
  }
  .ora-model-bar {
    background: #f3eefb;
    padding: 10px 14px;
    border-radius: 6px;
    margin-bottom: 16px;
    font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
    font-size: 13px;
    color: #2a2540;
  }
  /* Tighten sidebar spacing so it reads like PrivateGPT's panel */
  section[data-testid="stSidebar"] .stRadio > label { font-weight: 600; }
  section[data-testid="stSidebar"] hr { margin: 12px 0; }
</style>
<div class="ora-banner">
  <h1>🦙 &nbsp; OLLAMA-RAG-API</h1>
</div>
""",
    unsafe_allow_html=True,
)


def api_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=3).json()
    except Exception:
        return None


def list_ingested_files():
    if not SOURCE_DIR.exists():
        return []
    return sorted(
        f.name for f in SOURCE_DIR.iterdir()
        if f.is_file() and not f.name.startswith(".")
    )


def run_ingest():
    proc = subprocess.run(
        [sys.executable, "ingest.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def wipe_vectorstore():
    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)


def ask_api(query: str, timeout: int = 300) -> dict:
    r = requests.post(f"{API_URL}/ask", json={"query": query}, timeout=timeout)
    r.raise_for_status()
    return r.json()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None

# ---------- Sidebar ----------
with st.sidebar:
    st.subheader("Mode")
    mode_options = ["RAG", "Search", "Basic", "Summarize"]
    mode = st.radio(
        "Mode",
        mode_options,
        index=0,
        label_visibility="collapsed",
    )
    mode_help = {
        "RAG": "Get contextualized answers from your ingested files.",
        "Search": "Return retrieved chunks only — no LLM synthesis.",
        "Basic": "Talk to the model with no retrieval (coming soon).",
        "Summarize": "Summarize the ingested files (coming soon).",
    }
    st.caption(mode_help[mode])

    st.divider()

    st.subheader("Upload File(s)")
    uploaded = st.file_uploader(
        "Upload",
        accept_multiple_files=True,
        label_visibility="collapsed",
        type=SUPPORTED_EXTS,
    )
    if uploaded:
        if st.button("Ingest uploaded", type="primary", use_container_width=True):
            SOURCE_DIR.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                (SOURCE_DIR / f.name).write_bytes(f.getbuffer())
            with st.spinner(f"Ingesting {len(uploaded)} file(s)…"):
                rc, out, err = run_ingest()
            if rc == 0:
                st.success(f"Ingested {len(uploaded)} file(s).")
            else:
                st.error(f"Ingest failed:\n```\n{(err or out)[-800:]}\n```")
            st.rerun()

    st.divider()

    st.subheader("Ingested Files")
    files = list_ingested_files()
    if not files:
        st.info("No files yet. Upload one above to get started.")
    else:
        for fname in files:
            cols = st.columns([7, 1])
            cols[0].markdown(f"📄 `{fname}`")
            if cols[1].button("✕", key=f"del_{fname}", help=f"Delete {fname}"):
                (SOURCE_DIR / fname).unlink()
                wipe_vectorstore()
                if list_ingested_files():
                    with st.spinner("Rebuilding vectorstore…"):
                        run_ingest()
                st.rerun()

        if st.button(
            "🗑️ Delete ALL files",
            use_container_width=True,
            type="secondary",
        ):
            for f in SOURCE_DIR.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    f.unlink()
            wipe_vectorstore()
            st.rerun()

    st.divider()

    h = api_health()
    if h:
        st.success(f"✅ API up — `{h.get('model','?')}`")
    else:
        st.error(f"❌ API unreachable at {API_URL}")
    st.markdown(f"- [Swagger UI]({API_URL}/apidocs)")
    st.markdown(f"- [Raw spec]({API_URL}/apispec_1.json)")

# ---------- Model info bar ----------
model_name = (h or {}).get("model", "unknown")
st.markdown(
    f"""<div class="ora-model-bar">💬 &nbsp; LLM: <b>ollama</b> &nbsp;|&nbsp; """
    f"""Model: <b>{model_name}</b> &nbsp;|&nbsp; Mode: <b>{mode}</b></div>""",
    unsafe_allow_html=True,
)

# ---------- Chat history ----------
def render_sources(documents):
    with st.expander(f"📚 Sources ({len(documents)})"):
        for i, d in enumerate(documents, 1):
            st.markdown(f"**{i}. {d['source']}**")
            snippet = d["content"][:500] + ("…" if len(d["content"]) > 500 else "")
            st.code(snippet)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("documents"):
            render_sources(msg["documents"])


def fire_query(prompt: str, append_user_msg: bool = True):
    if mode in ("Basic", "Summarize"):
        st.warning(f"`{mode}` mode isn't wired up yet — falling back to RAG.")
    if append_user_msg:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                data = ask_api(prompt)
                docs = data.get("documents", [])
                if mode == "Search":
                    answer = "_Search mode — retrieved chunks only, no synthesis._"
                else:
                    answer = data.get("answer", "(no answer)")
                st.markdown(answer)
                if docs:
                    render_sources(docs)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "documents": docs}
                )
            except Exception as e:
                err = f"Request failed: {e}"
                st.error(err)
                st.session_state.messages.append(
                    {"role": "assistant", "content": err}
                )


# Honour a pending retry first; otherwise pick up chat input
pending = st.session_state.pending_query
st.session_state.pending_query = None

prompt = st.chat_input("Ask a question about your documents")

if pending:
    fire_query(pending, append_user_msg=False)
elif prompt:
    fire_query(prompt, append_user_msg=True)

# ---------- Retry / Undo / Clear ----------
def last_user_query():
    for m in reversed(st.session_state.messages):
        if m["role"] == "user":
            return m["content"]
    return None


col_retry, col_undo, col_clear = st.columns(3)

if col_retry.button(
    "🔄 Retry",
    use_container_width=True,
    disabled=last_user_query() is None,
    help="Re-run the last question with the current model + mode",
):
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "assistant":
        st.session_state.messages.pop()
    st.session_state.pending_query = last_user_query()
    st.rerun()

if col_undo.button(
    "↩️ Undo",
    use_container_width=True,
    disabled=not st.session_state.messages,
    help="Remove the last question and its answer",
):
    while (
        st.session_state.messages
        and st.session_state.messages[-1]["role"] == "assistant"
    ):
        st.session_state.messages.pop()
    if st.session_state.messages:
        st.session_state.messages.pop()
    st.rerun()

if col_clear.button(
    "🗑️ Clear",
    use_container_width=True,
    disabled=not st.session_state.messages,
    help="Wipe the chat history",
):
    st.session_state.messages = []
    st.rerun()
