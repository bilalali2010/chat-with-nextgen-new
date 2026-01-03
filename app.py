import streamlit as st
import os
import requests
import PyPDF2
import pandas as pd
from collections import Counter
from datetime import datetime

# -----------------------------
# Environment Variables
# -----------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ADMIN_TRIGGER = os.getenv("ADMIN_TRIGGER", "@admin")  # fallback

if not OPENROUTER_API_KEY:
    st.error("⚠️ OPENROUTER_API_KEY is missing. Add it in Railway Variables.")
    st.stop()

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(
    page_title="ASK ANYTHING ABOUT BILAL",
    layout="centered"
)

# -----------------------------
# Custom Header
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
<div class="chat-header">
   CHAT WITH NEXTGEN
</div>
""", unsafe_allow_html=True)

# -----------------------------
# Knowledge directory
# -----------------------------
KNOWLEDGE_DIR = "knowledge_pdfs"
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
MAX_CONTEXT = 4500
KNOWLEDGE_FILE = "knowledge.txt"

# -----------------------------
# Session State Initialization
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
# Load Knowledge
# -----------------------------
knowledge = ""
if os.path.exists(KNOWLEDGE_FILE):
    with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
        knowledge = f.read()

# -----------------------------
# Admin Panel Sidebar (Hidden Password Input)
# -----------------------------
if not st.session_state.admin_unlocked:
    st.sidebar.header("🔐 Admin Login")
    password = st.sidebar.text_input(
        "Enter Admin Password",
        type="password"
    )
    if password:
        if password.strip() == ADMIN_TRIGGER:
            st.session_state.admin_unlocked = True
            st.sidebar.success("🔐 Admin panel unlocked!")
            st.experimental_rerun()
        else:
            st.sidebar.error("❌ Incorrect password")

# -----------------------------
# Display Chat Messages
# -----------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# -----------------------------
# Chat Input
# -----------------------------
user_input = st.chat_input("Message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if not knowledge:
        bot_reply = "⚠️ No knowledge uploaded yet. Admin must upload PDFs first."
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
                        "You are a helpful AI assistant. "
                        "Answer SHORT (1-2 sentences) and ONLY using the document. "
                        "If the answer is not present, reply exactly: 'Information not available.'"
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
                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    data = response.json()
                    bot_reply = data["choices"][0]["message"]["content"] if "choices" in data else "⚠️ Error generating response."
                except Exception as e:
                    bot_reply = f"⚠️ Error generating response: {e}"

                st.markdown(bot_reply)

    st.session_state.messages.append(
        {"role": "assistant", "content": bot_reply}
    )
    st.session_state.chat_history.append(
        (user_input, bot_reply, datetime.now())
    )

# -----------------------------
# Admin Panel Sidebar (After Unlock)
# -----------------------------
if st.session_state.admin_unlocked:
    st.sidebar.header("🔐 Admin Panel")

    # ---- PDF Upload ----
    uploaded_files = st.sidebar.file_uploader(
        "Upload Knowledge PDF(s)",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        combined_text = ""
        for file in uploaded_files:
            try:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    combined_text += page.extract_text() or ""
            except Exception as e:
                st.sidebar.error(f"⚠️ Error reading {file.name}: {e}")

        combined_text = combined_text[:MAX_CONTEXT]

        if combined_text:
            with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
                f.write(combined_text)
            st.sidebar.success("✅ Knowledge updated successfully")
        else:
            st.sidebar.warning("⚠️ Uploaded PDFs had no text.")

    # ---- Chat Analytics ----
    st.sidebar.subheader("Chat Statistics")
    total_questions = len(st.session_state.chat_history)
    st.sidebar.markdown(f"**Total Questions:** {total_questions}")

    if total_questions > 0:
        questions = [q for q, _, _ in st.session_state.chat_history]
        freq = Counter(questions).most_common(5)

        st.sidebar.markdown("**Top 5 Questions:**")
        for q, count in freq:
            st.sidebar.markdown(f"- {q} ({count})")

        last_active = st.session_state.chat_history[-1][2].strftime("%Y-%m-%d %H:%M:%S")
        st.sidebar.markdown(f"**Last Active:** {last_active}")

        if st.sidebar.button("Export Chat History"):
            df = pd.DataFrame(
                st.session_state.chat_history,
                columns=["Question", "Answer", "Timestamp"]
            )
            df.to_csv("chat_history.csv", index=False)
            st.sidebar.success("✅ Chat history exported")
