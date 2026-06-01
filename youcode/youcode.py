import streamlit as st
import ollama
import time

# Initialize lightweight utilities
if "reports" not in st.session_state:
    st.session_state.reports = []
if "clipboard" not in st.session_state:
    st.session_state.clipboard = ""

# ── 1. PAGE CONFIG ──────────────────────────────────────────────────────────
st.set_page_config(page_title="YOUCODE", page_icon="🧠", layout="centered")
st.title("🧠 YOUCODE — AI Code Explainer")

# ── 2. SIDEBAR CONTROLS ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    model = st.selectbox("🤖 Model", ["llama3", "codellama", "mistral", "gemma"], index=3)
    temperature = st.slider("🌡️ Temperature", 0.0, 1.0, 0.25, 0.05)
    ctx_window = st.slider("🪟 Context Messages", 1, 20, 6, 1)
    persona = st.selectbox("🎭 Persona", ["Code Teacher", "Code Reviewer", "Subject Tutor"])
    compact = st.checkbox("⚡ Compact responses (faster)", value=True)
    quick_mode = st.checkbox("⏩ Quick mode (short replies)", value=False)
    max_tokens = st.slider("✂️ Max tokens (response length)", 50, 1024, 256, 50)
    st.divider()
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    # quick access to clipboard and reports
    with st.expander("📎 Clipboard & Reports", expanded=False):
        st.text_area("Session clipboard", value=st.session_state.clipboard, height=80)
        st.write("Reported messages:")
        for r in st.session_state.reports[::-1]:
            st.write(f"- {r.get('time')}: {r.get('content')[:120]}")

# ── 3. SYSTEM PROMPT / PERSONA ───────────────────────────────────────────────
personas = {
    "Code Teacher": (
        "You are YOUCODE, a patient coding teacher. Identify the language, "
        "then explain each line clearly for beginners with simple analogies and emojis."
    ),
    "Code Reviewer": (
        "You are YOUCODE, an expert code reviewer. Identify the language, "
        "explain each line, flag issues, and suggest concise improvements."
    ),
    "Subject Tutor": (
        "You are YOUCODE, a subject tutor. Identify the language, explain each line's concept, "
        "and connect it to broader CS principles."
    ),
}
system_prompt = personas[persona]
if 'compact' in locals() and compact:
    # Shorten system prompt further to reduce token usage and speed responses
    system_prompt = system_prompt.split('.', 1)[0]
if 'quick_mode' in locals() and quick_mode:
    # enforce concise system prompt and smaller responses
    system_prompt = system_prompt.split('.', 1)[0]
    max_tokens = min(max_tokens, 150)

# ── 4. INITIALIZE MEMORY ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── 4A. DEFINE HELPER FUNCTION ──────────────────────────────────────────────
def call_model(api_messages, model, temperature, max_tokens, placeholder=None):
    """Call Ollama with streaming and buffered UI updates. Returns the full response text."""
    if placeholder is None:
        placeholder = st.empty()
    response_text = ""
    try:
        options = {"temperature": temperature, "top_p": 0.9, "max_tokens": max_tokens}
        stream = ollama.chat(model=model, messages=api_messages, stream=True, options=options)
        buffer = ""
        last_update = time.time()
        for chunk in stream:
            part = chunk.get("message", {}).get("content", "")
            if not part:
                continue
            response_text += part
            buffer += part
            if len(buffer) >= 80 or (time.time() - last_update) > 0.25:
                placeholder.markdown(response_text)
                buffer = ""
                last_update = time.time()
        if buffer:
            placeholder.markdown(response_text)
    except Exception as e:
        try:
            options = {"temperature": temperature, "top_p": 0.9, "max_tokens": max_tokens}
            resp = ollama.chat(model=model, messages=api_messages, options=options)
            response_text = resp.get("message", {}).get("content", str(resp))
            placeholder.markdown(response_text)
        except Exception as e2:
            response_text = f"Error: {e} | {e2}"
            placeholder.markdown(response_text)
    return response_text

# ── 5. DISPLAY CHAT HISTORY ─────────────────────────────────────────────────
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # add per-response actions for assistant messages
        if msg["role"] == "assistant":
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                if st.button("🔁 Repeat", key=f"repeat_{i}"):
                    # find the previous user message to repeat
                    prev_user = None
                    for prev in reversed(st.session_state.messages[:i]):
                        if prev.get("role") == "user":
                            prev_user = prev.get("content")
                            break
                    if prev_user:
                        st.session_state.messages.append({"role": "user", "content": prev_user})
                        with st.chat_message("user"):
                            st.markdown(prev_user)
                        # build history and call model immediately
                        history = st.session_state.messages[-ctx_window:]
                        api_messages = [{"role": "system", "content": system_prompt}] + history
                        with st.chat_message("assistant"):
                            placeholder = st.empty()
                            response_text = call_model(api_messages, model, temperature, max_tokens, placeholder)
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
            with c2:
                if st.button("📋 Copy", key=f"copy_{i}"):
                    st.session_state.clipboard = msg.get("content", "")
                    st.success("Copied to session clipboard (open sidebar to paste)")
            with c3:
                if st.button("🚩 Report", key=f"report_{i}"):
                    st.session_state.reports.append({"index": i, "content": msg.get("content", ""), "time": time.ctime()})
                    st.warning("Message reported — thanks!")

# Mobile-friendly CSS tweaks
st.markdown(
    """
    <style>
    /* make chat blocks and text adapt to small screens */
    .stApp .block-container{padding-left:0.8rem;padding-right:0.8rem}
    .stChatMessage{font-size:1.05rem}
    @media (max-width:600px){
        .stChatMessage{font-size:1.0rem}
        .css-1d391kg {padding: 0 0.6rem;} /* layout tweaks for mobile */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 6. USER INPUT ───────────────────────────────────────────────────────────
if prompt := st.chat_input("Paste your code or ask a question…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # ── 7. CALL OLLAMA WITH STREAMING (improved for faster, incremental UI) ──
    history = st.session_state.messages[-ctx_window:]
    api_messages = [{"role": "system", "content": system_prompt}] + history

    with st.chat_message("assistant"):
        placeholder = st.empty()
        response_text = call_model(api_messages, model, temperature, max_tokens, placeholder)

    st.session_state.messages.append({"role": "assistant", "content": response_text})