import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:5001")

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
  section[data-testid="stSidebar"] .stRadio > label { font-weight: 600; }
  section[data-testid="stSidebar"] hr { margin: 12px 0; }
</style>
<div class="ora-banner">
  <h1>🦙 &nbsp; OLLAMA-RAG-API</h1>
</div>
""",
    unsafe_allow_html=True,
)


# --------------------------- API client ---------------------------

def api_health():
    try:
        return requests.get(f"{API_URL}/health", timeout=3).json()
    except Exception:
        return None


def api_list_files():
    try:
        return requests.get(f"{API_URL}/files", timeout=5).json().get("files", [])
    except Exception:
        return []


def api_upload(uploaded_file):
    files = {"file": (uploaded_file.name, uploaded_file.getbuffer(), uploaded_file.type or "application/octet-stream")}
    return requests.post(f"{API_URL}/ingest", files=files, timeout=600)


def api_delete(filename: str):
    return requests.delete(f"{API_URL}/files/{filename}", timeout=60)


def api_ask(query: str):
    return requests.post(f"{API_URL}/ask", json={"query": query}, timeout=300).json()


def api_chat(query: str):
    return requests.post(f"{API_URL}/chat", json={"query": query}, timeout=300).json()


def api_summarize(file: str | None = None):
    body = {"file": file} if file else {}
    return requests.post(f"{API_URL}/summarize", json=body, timeout=600).json()


# --------------------------- session state ---------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None
if "pending_mode" not in st.session_state:
    st.session_state.pending_mode = None


# --------------------------- sidebar ---------------------------

with st.sidebar:
    st.subheader("Mode")
    mode_options = ["RAG", "Search", "Basic", "Summarize"]
    mode = st.radio("Mode", mode_options, index=0, label_visibility="collapsed")
    mode_help = {
        "RAG": "Get contextualized answers from your ingested files.",
        "Search": "Return retrieved chunks only — no LLM synthesis.",
        "Basic": "Talk to the model directly, no retrieval.",
        "Summarize": "Summarize a selected file (or the whole corpus).",
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
            ok, fail = 0, 0
            with st.spinner(f"Uploading {len(uploaded)} file(s)…"):
                for f in uploaded:
                    try:
                        r = api_upload(f)
                        if r.status_code == 200:
                            ok += 1
                        else:
                            fail += 1
                            st.error(f"{f.name}: {r.json().get('error', r.text)}")
                    except Exception as e:
                        fail += 1
                        st.error(f"{f.name}: {e}")
            if ok:
                st.success(f"Ingested {ok} file(s).")
            if fail == 0:
                st.rerun()

    st.divider()

    st.subheader("Ingested Files")
    files = api_list_files()
    if not files:
        st.info("No files yet. Upload one above to get started.")
        selected_file = None
    else:
        for f in files:
            cols = st.columns([6, 2, 1])
            cols[0].markdown(f"📄 `{f['name']}`")
            cols[1].caption(f"{f['chunks']} chunks")
            if cols[2].button("✕", key=f"del_{f['name']}", help=f"Delete {f['name']}"):
                with st.spinner(f"Deleting {f['name']}…"):
                    api_delete(f["name"])
                st.rerun()

        if st.button("🗑️ Delete ALL files", use_container_width=True, type="secondary"):
            with st.spinner("Deleting all files…"):
                for f in files:
                    api_delete(f["name"])
            st.rerun()

    # Selector used by Summarize mode (and could power future per-file ask)
    selected_file = None
    if files and mode == "Summarize":
        st.divider()
        st.subheader("Summarize target")
        choices = ["(all files)"] + [f["name"] for f in files]
        choice = st.selectbox("Pick a file or summarize everything", choices, label_visibility="collapsed")
        selected_file = None if choice == "(all files)" else choice

    st.divider()

    h = api_health()
    if h:
        st.success(f"✅ API up — `{h.get('model','?')}`")
    else:
        st.error(f"❌ API unreachable at {API_URL}")
        if st.button("🔄 Recheck", use_container_width=True, key="recheck_health"):
            st.rerun()
    st.markdown(f"- [Swagger UI]({API_URL}/apidocs)")
    st.markdown(f"- [Raw spec]({API_URL}/apispec_1.json)")


# --------------------------- model info bar ---------------------------

model_name = (h or {}).get("model", "unknown")
st.markdown(
    f"""<div class="ora-model-bar">💬 &nbsp; LLM: <b>ollama</b> &nbsp;|&nbsp; """
    f"""Model: <b>{model_name}</b> &nbsp;|&nbsp; Mode: <b>{mode}</b></div>""",
    unsafe_allow_html=True,
)


# --------------------------- chat rendering ---------------------------

def render_sources(documents):
    if not documents:
        return
    with st.expander(f"📚 Sources ({len(documents)})"):
        for i, d in enumerate(documents, 1):
            st.markdown(f"**{i}. {d['source']}**")
            snippet = d["content"][:500] + ("…" if len(d["content"]) > 500 else "")
            st.code(snippet)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        render_sources(msg.get("documents") or [])


# --------------------------- query dispatcher ---------------------------

def fire_query(prompt: str, run_mode: str, target_file: str | None, append_user_msg: bool):
    if append_user_msg:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                docs = []
                if run_mode == "RAG":
                    data = api_ask(prompt)
                    answer = data.get("answer", "(no answer)")
                    docs = data.get("documents", [])
                elif run_mode == "Search":
                    data = api_ask(prompt)
                    docs = data.get("documents", [])
                    answer = f"_Search mode — {len(docs)} chunks retrieved, no synthesis._"
                elif run_mode == "Basic":
                    data = api_chat(prompt)
                    answer = data.get("answer", "(no answer)")
                elif run_mode == "Summarize":
                    data = api_summarize(target_file)
                    truncated = " _(truncated)_" if data.get("truncated") else ""
                    scope = data.get("file", "all")
                    answer = (
                        f"**Summary of `{scope}`** "
                        f"(used {data.get('chunks_used', '?')} chunks{truncated})\n\n"
                        f"{data.get('answer', '(no answer)')}"
                    )
                else:
                    answer = f"Unknown mode: {run_mode}"

                st.markdown(answer)
                render_sources(docs)
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "documents": docs}
                )
            except Exception as e:
                err = f"Request failed: {e}"
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})


pending_q = st.session_state.pending_query
pending_m = st.session_state.pending_mode
st.session_state.pending_query = None
st.session_state.pending_mode = None

# Summarize mode auto-fires on click (no chat input needed)
if mode == "Summarize":
    if st.button("📝 Generate summary", type="primary"):
        scope = selected_file or "all files"
        fire_query(f"Summarize {scope}", "Summarize", selected_file, append_user_msg=True)

prompt = st.chat_input(
    "Ask a question…" if mode != "Summarize" else "(Summarize mode — use the button above)",
    disabled=(mode == "Summarize"),
)

if pending_q:
    fire_query(pending_q, pending_m or mode, selected_file, append_user_msg=False)
elif prompt:
    fire_query(prompt, mode, selected_file, append_user_msg=True)


# --------------------------- retry / undo / clear ---------------------------

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
    st.session_state.pending_mode = mode
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
