import streamlit as st
import os
import requests
import PyPDF2
from datetime import datetime
import random

# -----------------------------
# CONFIG
# -----------------------------
ADMIN_PASSWORD = "@supersecret"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    st.error("⚠️ OPENROUTER_API_KEY missing")
    st.stop()

KNOWLEDGE_FILE = "knowledge.txt"
MAX_CONTEXT = 4500
FALLBACK_MESSAGES = [
    "Hmm, I’m not sure about that, but I can help you figure it out!",
    "Good question! I don’t have that info yet, but here’s something useful…",
    "I don’t know exactly, but let me give you a tip that might help!",
    "That’s tricky! Let’s explore together."
]

FUN_ENDINGS = [
    "😎 Hope that helps!",
    "🔥 Did you know this?",
    "🤔 Interesting, right?",
    "✨ Just a tip!"
]

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="CHAT WITH NEXTGEN",
    layout="centered"
)

# -----------------------------
# FIN-STYLE CSS
# -----------------------------
st.markdown("""
<style>
.chat-container {
    max-width: 700px;
    margin: auto;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #ddd;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    padding: 10px;
    max-height: 600px;
    overflow-y: auto;
}
.chat-header {
    background: linear-gradient(90deg, #4285f4, #5a95f5);
    padding: 15px;
    color: white;
    font-weight: bold;
    font-size: 18px;
    text-align: center;
    border-radius: 10px;
    margin-bottom: 10px;
}
div[data-testid="stChatMessage"][data-role="user"] > div {
    background-color: #0b93f6;
    color: white;
    border-radius: 20px;
    padding: 10px 15px;
    margin: 5px 0;
    max-width: 75%;
}
div[data-testid="stChatMessage"][data-role="assistant"] > div {
    background-color: #e5e5ea;
    color: black;
    border-radius: 20px;
    padding: 10px 15px;
    margin: 5px 0;
    max-width: 75%;
}
.stTextInput>div>div>input {
    border-radius: 20px;
    padding: 10px 15px;
}
div[data-role="user"]::before { content: "👤"; margin-right: 5px; }
div[data-role="assistant"]::before { content: "🤖"; margin-right: 5px; }
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SESSION STATE INITIALIZATION
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

# Add greeting only once
if len(st.session_state.messages) == 0:
    st.session_state.messages.append(
        {"role": "assistant", "content": "Hi! I’m NEXTGEN, your assistant. Ask me anything!"}
    )

# -----------------------------
# LOAD KNOWLEDGE
# -----------------------------
knowledge = ""
if os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        knowledge = f.read()

# -----------------------------
# ADMIN PANEL
# -----------------------------
IS_ADMIN_PAGE = "admin" in st.query_params

if IS_ADMIN_PAGE:
    st.sidebar.header("🔐 Admin Panel")
    if not st.session_state.admin_unlocked:
        pwd_input = st.sidebar.text_input("Enter admin password", type="password")
        if st.sidebar.button("Unlock Admin"):
            if pwd_input == ADMIN_PASSWORD:
                st.session_state.admin_unlocked = True
                st.sidebar.success("Admin unlocked!")
                st.experimental_rerun()
            else:
                st.sidebar.error("Wrong password!")
    else:
        st.sidebar.success("Admin Unlocked")
        uploaded_pdfs = st.sidebar.file_uploader(
            "Upload PDF Knowledge", type="pdf", accept_multiple_files=True
        )
        text_knowledge = st.sidebar.text_area(
            "Add Training Text", height=150, placeholder="Paste custom knowledge here..."
        )
        if st.sidebar.button("💾 Save Knowledge"):
            combined_text = ""
            if uploaded_pdfs:
                for file in uploaded_pdfs:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        try:
                            combined_text += page.extract_text() or ""
                        except:
                            continue
            if text_knowledge.strip():
                combined_text += "\n\n" + text_knowledge.strip()
            combined_text = combined_text[:MAX_CONTEXT]
            if combined_text.strip():
                with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                    f.write(combined_text)
                st.sidebar.success("✅ Knowledge saved")
            else:
                st.sidebar.warning("⚠️ No content to save")

# -----------------------------
# CHAT DISPLAY FUNCTION
# -----------------------------
def render_chat():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    st.markdown('<div class="chat-header">CHAT WITH NEXTGEN</div>', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# CHAT INPUT
# -----------------------------
user_input = st.chat_input("Ask NEXTGEN anything...")

if user_input:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history.append((user_input, "", datetime.now()))

    # Prepare context for API
    MAX_CONTEXT_CHARS = 2000
    recent_chat_text = ""
    for u, b, _ in reversed(st.session_state.chat_history):
        pair = f"User: {u}\nBot: {b}\n"
        if len(recent_chat_text) + len(pair) > MAX_CONTEXT_CHARS:
            break
        recent_chat_text = pair + recent_chat_text

    prompt_content = ""
    if knowledge.strip():
        prompt_content += f"Document:\n{knowledge}\n\n"
    prompt_content += f"Recent chat:\n{recent_chat_text}\n\nQuestion:\n{user_input}"

    payload = {
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "messages": [
            {"role": "system",
             "content": (
                 "You are CHAT WITH NEXTGEN assistant. "
                 "Answer concisely using the document if possible. "
                 "If the information is missing, respond in a helpful, friendly, or entertaining way. "
                 "Never reply empty or 'Information not available'. Always engage the user."
             )
             },
            {"role": "user", "content": prompt_content}
        ],
        "max_output_tokens": 150,
        "temperature": 0.4
    }

    # Call OpenRouter API
    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )
        data = res.json()
        bot_reply = data["choices"][0]["message"]["content"].strip()
        if not bot_reply:
            bot_reply = random.choice(FALLBACK_MESSAGES) + " " + random.choice(FUN_ENDINGS)
    except Exception:
        bot_reply = random.choice(FALLBACK_MESSAGES) + " " + random.choice(FUN_ENDINGS)

    # Append bot reply
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.session_state.chat_history[-1] = (user_input, bot_reply, datetime.now())

# Finally render chat **once**, after all updates
render_chat()
