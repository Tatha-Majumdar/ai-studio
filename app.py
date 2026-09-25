import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import re
import json

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"
HISTORY_FILE = "chat_history.json"

# ============ SESSION STATE ============
DEFAULTS = {
    "messages": [],
    "current_track": None,
    "show_code_editor": False,
    "code_exercise": "",
    "code_content": "# Type your code here",
    "code_output": "",
    "code_error": "",
    "code_ran": False,
    "current_plot": None,
    "has_plot": False,
    "show_quiz": False,
    "quiz_question": "",
    "quiz_options": [],
    "loaded": False,
    "start_requested": None,
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ============ PERSISTENCE ============
def save_history():
    try:
        data = {
            "messages": st.session_state.get("messages", []),
            "current_track": st.session_state.get("current_track"),
            "show_code_editor": st.session_state.get("show_code_editor", False),
            "code_exercise": st.session_state.get("code_exercise", ""),
            "code_content": st.session_state.get("code_content", ""),
            "code_output": st.session_state.get("code_output", ""),
            "code_error": st.session_state.get("code_error", ""),
            "code_ran": st.session_state.get("code_ran", False),
        }
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except:
        pass

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in st.session_state:
                    st.session_state[key] = value
            return True
    except:
        pass
    return False

if not st.session_state.get("loaded", False):
    load_history()
    st.session_state["loaded"] = True

def clear_all():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except:
        pass
    for key, default in DEFAULTS.items():
        st.session_state[key] = default

# ============ API KEY ============
API_KEY = ""
try:
    API_KEY = st.secrets.get("STEPFUN_API_KEY", "")
except:
    pass
if not API_KEY:
    API_KEY = os.environ.get("STEPFUN_API_KEY", "")

# ============ MENTOR PROMPT ============
MENTOR_PROMPT = (
    "You are a senior engineering mentor. You teach Topology Optimization and System Design. "
    "The student may have zero coding experience.\n\n"
    "CRITICAL: Never say imagine, picture, or visualize. The student must SEE everything. "
    "Always provide matplotlib code, printed output, concrete examples, or ASCII diagrams.\n\n"
    "Use [PRACTICE] at the end of a message to give a coding exercise.\n"
    "Use [QUIZ] Question | Option A | Option B for quizzes.\n\n"
    "Rules: One concept at a time. Always show visuals. Code must run. "
    "Keep responses under 200 words. Track what was taught.\n\n"
    "For Topology Optimization: build a SIMP solver, teach Python as needed.\n"
    "For System Design: build real systems, teach coding as needed.\n\n"
    "Start: Ask about coding experience, then begin lesson 1 with a visual example."
)

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============ CSS ============
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    background: #0A0A0A;
    font-family: 'Inter', sans-serif;
    color: #F5F5F5;
}

#MainMenu, footer, header, [data-testid="stSidebar"], [data-testid="stToolbar"] {
    display: none !important;
}

.block-container {
    padding-top: 1rem;
    max-width: 720px;
}

.app-header {
    text-align: center;
    padding: 1rem 0;
    border-bottom: 1px solid #1A1A1A;
    margin-bottom: 0.5rem;
}

.app-header h1 {
    font-size: 1.75rem;
    font-weight: 800;
    color: #F5F5F5;
    margin: 0;
}

.app-header p {
    font-size: 0.8125rem;
    color: #6E6E73;
    margin: 0.25rem 0 0 0;
}

[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.25rem 0 !important;
}

[data-testid="stChatMessageAvatar"],
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"],
[data-testid="chatAvatar"] {
    display: none !important;
}

[data-testid="stChatMessageContent"] {
    background: #1C1C1E;
    border: 1px solid #2A2A2A;
    border-radius: 18px;
    border-bottom-left-radius: 4px;
    padding: 0.875rem 1.125rem;
    font-size: 0.9375rem;
    line-height: 1.65;
    color: #F5F5F5;
}

[data-testid="stChatMessage"] pre {
    background: #0A0A0A !important;
    border: 1px solid #2A2A2A;
    border-radius: 10px;
    padding: 0.875rem;
    font-size: 0.8125rem;
    color: #E0E0E0;
}

[data-testid="stChatMessage"] code {
    background: #262626;
    color: #7DD3FC;
    padding: 2px 6px;
