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
/* Chat container */
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

/* Chat header */
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

/* User messages */
div[data-testid="stChatMessage"][data-role="user"] > div {
    background-color: #0b93f6;
    color: white;
    border-radius: 20px;
    padding: 10px 15px;
    margin: 5px 0;
    max-width: 75%;
}

/* Assistant messages */
div[data-testid="stChatMessage"][data-role="assistant"] > div {
    background-color: #e5e5ea;
    color: black;
    border-radius: 20px;
    padding: 10px 15px;
    margin: 5px 0;
    max-width: 75%;
}

/* Input box */
.stTextInput>div>div>input {
    border-radius: 20px;
    padding: 10px 15px;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# SECRET ADMIN URL
# -----------------------------
query_params = st.query_params
IS_ADMIN_PAGE = query_params.get("admin") == ["1"]

# -----------------------------
# SESSION STATE
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I’m here to help you. Ask me anything about Bilal!"}
    ]

if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

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
if IS_ADMIN_PAGE:
    st.sidebar.header("🔐 Admin Panel")

    if st.session_state.admin_unlocked:
        st.sidebar.success("Admin Unlocked")
    else:
        st.sidebar.warning("Admin Locked")
        st.sidebar.markdown("**Type password in chat to unlock**")

    uploaded_pdfs = st.sidebar.file_uploader(
        "Upload PDF Knowledge",
        type="pdf",
        accept_multiple_files=True,
        disabled=not st.session_state.admin_unlocked
    )

    text_knowledge = st.sidebar.text_area(
        "Add Training Text",
        height=150,
        placeholder="Paste custom knowledge here...",
        disabled=not st.session_state.admin_unlocked
    )

    if st.sidebar.button("💾 Save Knowledge", disabled=not st.session_state.admin_unlocked):
        combined_text = ""

        if uploaded_pdfs:
            for file in uploaded_pdfs:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    combined_text += page.extract_text() or ""

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
# CHAT DISPLAY
# -----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<div class="chat-header">CHAT WITH NEXTGEN</div>', unsafe_allow_html=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown('</div>', unsafe_allow_html=True)

# -----------------------------
# CHAT INPUT
# -----------------------------
user_input = st.chat_input("Message...")

if user_input:
    # 🔐 ADMIN UNLOCK
    if IS_ADMIN_PAGE and user_input.strip() == ADMIN_PASSWORD:
        st.session_state.admin_unlocked = True
        st.session_state.messages.append({
            "role": "assistant",
            "content": "🔐 Admin panel unlocked."
        })
        st.experimental_rerun()

    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history.append((user_input, "", datetime.now()))

    # Prepare API payload
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # Include recent chat for context
    recent_chat = st.session_state.chat_history[-3:]
    context_messages = "\n".join([f"User: {u}\nBot: {b}" for u, b, t in recent_chat])

    prompt_content = f"Document:\n{knowledge}\n\nRecent chat:\n{context_messages}\n\nQuestion:\n{user_input}"

    payload = {
        "model": "nvidia/nemotron-3-nano-30b-a3b:free",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer concisely using the document if possible. "
                    "If the information is missing, respond in a helpful, friendly, or entertaining way. "
                    "Never reply empty or 'Information not available'. Always engage the user."
                )
            },
            {"role": "user", "content": prompt_content}
        ],
        "max_output_tokens": 80,
        "temperature": 0.4
    }

    # Call OpenRouter API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                res = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                data = res.json()
                bot_reply = data["choices"][0]["message"]["content"].strip()
                if not bot_reply:
                    bot_reply = random.choice(FALLBACK_MESSAGES)
            except Exception as e:
                bot_reply = (
                    "Oops! Something went wrong while fetching the answer. "
                    "But I'm still here to help, feel free to ask anything!"
                )

            st.markdown(bot_reply)
            # Update session state
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            st.session_state.chat_history[-1] = (user_input, bot_reply, datetime.now())
