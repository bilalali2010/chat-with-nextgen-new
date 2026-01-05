import streamlit as st
import os
import requests
import PyPDF2
import pandas as pd
from datetime import datetime

# -----------------------------
# CONFIG
# -----------------------------
ADMIN_PASSWORD = "@supersecret"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

if not OPENROUTER_API_KEY:
    st.error("⚠️ OPENROUTER_API_KEY missing")
    st.stop()

# -----------------------------
# PAGE CONFIG
# -----------------------------
st.set_page_config(
    page_title="ASK ANYTHING ABOUT BILAL",
    layout="centered"
)

# -----------------------------
# SECRET ADMIN URL
# -----------------------------
query_params = st.query_params
IS_ADMIN_PAGE = query_params.get("admin") == "1"

# -----------------------------
# HEADER
# -----------------------------
st.markdown("""
<style>
.chat-header {
    background: linear-gradient(90deg, #4285f4, #5a95f5);
    padding: 14px;
    color: white;
    font-size: 18px;
    font-weight: bold;
    border-radius: 10px;
    text-align: center;
}
</style>
<div class="chat-header">CHAT WITH NEXTGEN</div>
""", unsafe_allow_html=True)

# -----------------------------
# FILE CONFIG
# -----------------------------
KNOWLEDGE_FILE = "knowledge.txt"
MAX_CONTEXT = 4500

# -----------------------------
# SESSION STATE
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! What can I help you with?"}
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
# ADMIN PANEL (SECRET URL)
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
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

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
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if not knowledge:
        bot_reply = "⚠️ No knowledge uploaded yet."
    else:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "nvidia/nemotron-3-nano-30b-a3b:free",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Answer SHORT (1–2 sentences) ONLY using the document. "
                        "If the answer is not present, reply exactly: Information not available."
                    )
                },
                {
                    "role": "user",
                    "content": f"Document:\n{knowledge}\n\nQuestion:\n{user_input}"
                }
            ],
            "max_output_tokens": 80,
            "temperature": 0.2
        }

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
                    bot_reply = data["choices"][0]["message"]["content"]
                except Exception as e:
                    bot_reply = f"⚠️ Error: {e}"

                st.markdown(bot_reply)

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.session_state.chat_history.append((user_input, bot_reply, datetime.now()))
