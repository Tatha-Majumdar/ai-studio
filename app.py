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
    border-radius: 4px;
}

[data-testid="stChatMessage"] pre code {
    background: transparent;
    padding: 0;
    color: inherit;
}

[data-testid="stChatMessage"] strong {
    color: #FFFFFF;
}

[data-testid="stChatInput"] textarea {
    background: #141414 !important;
    border: 1px solid #2A2A2A !important;
    border-radius: 18px !important;
    color: #F5F5F5 !important;
    font-family: 'Inter', sans-serif !important;
}

.stButton > button {
    background: #0A84FF;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 0.625rem 1.25rem;
    font-weight: 600;
    font-size: 0.875rem;
    font-family: 'Inter', sans-serif;
}

.stButton > button:hover {
    background: #409CFF;
}

.output-box {
    background: #0D0D0D;
    border: 1px solid #30D15830;
    border-radius: 10px;
    padding: 0.875rem;
    font-family: monospace;
    font-size: 0.8125rem;
    color: #30D158;
    white-space: pre-wrap;
    margin: 0.5rem 0;
}

.error-box {
    background: #1A0D0D;
    border: 1px solid #FF453A30;
    border-radius: 10px;
    padding: 0.875rem;
    font-family: monospace;
    font-size: 0.8125rem;
    color: #FF453A;
    white-space: pre-wrap;
    margin: 0.5rem 0;
}

.project-card {
    background: #141414;
    border: 1px solid #262626;
    border-radius: 16px;
    padding: 1.5rem;
    margin: 0.75rem 0;
    text-align: center;
}

.project-card h3 {
    color: #F5F5F5;
    font-size: 1.125rem;
    font-weight: 700;
    margin: 0 0 0.375rem 0;
}

.project-card p {
    color: #8E8E93;
    font-size: 0.8125rem;
    margin: 0;
}

.section-label {
    font-size: 0.6875rem;
    font-weight: 700;
    color: #0A84FF;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 1rem 0 0.5rem 0;
}

[data-testid="stInfo"] {
    background: #0D0D0D;
    border: 1px solid #0A84FF;
    border-radius: 10px;
    color: #A0C4FF;
}

hr { border: none; height: 1px; background: #1A1A1A; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# ============ HELPER FUNCTIONS ============
def safe_clean(text):
    if not text or not isinstance(text, str):
        return ""
    try:
        clean = re.sub(r'\[PRACTICE\].*', '', text, flags=re.DOTALL)
        clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
        return clean.strip()
    except:
        return str(text) if text else ""

def parse_ai_response(text):
    if not text or not isinstance(text, str):
        return
    try:
        if "[PRACTICE]" in text:
            match = re.search(r'\[PRACTICE\]\s*(.+)', text, re.DOTALL)
            if match:
                st.session_state.show_code_editor = True
                st.session_state.code_exercise = match.group(1).strip()
                st.session_state.code_ran = False
                st.session_state.code_output = ""
                st.session_state.code_error = ""
    except:
        pass
    try:
        if "[QUIZ]" in text:
            parts = text.split("[QUIZ]")[1].split("|")
            if len(parts) >= 2:
                st.session_state.show_quiz = True
                st.session_state.quiz_question = parts[0].strip()
                st.session_state.quiz_options = [p.strip() for p in parts[1:] if p.strip()]
    except:
        pass

def execute_code(code):
    if not code:
        return "", "No code", False, None
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_cap = io.StringIO()
    stderr_cap = io.StringIO()
    
    namespace = {"__name__": "__main__"}
    
    try:
        import math
        namespace['math'] = math
    except:
        pass
    try:
        import numpy as np
        namespace['np'] = np
    except:
        pass
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        namespace['plt'] = plt
    except:
        pass
    
    try:
        with contextlib.redirect_stdout(stdout_cap):
            with contextlib.redirect_stderr(stderr_cap):
                exec(code, namespace)
        
        output = stdout_cap.getvalue()
        error = stderr_cap.getvalue()
        
        has_fig = False
        fig = None
        try:
            if 'plt' in namespace:
                nums = plt.get_fignums()
                if nums:
                    has_fig = True
                    fig = plt.figure(nums[0])
        except:
            pass
        
        return output, error, has_fig, fig
    except:
        output = stdout_cap.getvalue()
        error = traceback.format_exc()
        return output, error, False, None
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def call_api(user_message):
    """Simple non-streaming API call. Returns response text or error."""
    
    if not API_KEY:
        return "ERROR: No API key found. Go to Settings > Secrets and add STEPFUN_API_KEY."
    
    try:
        client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        
        for msg in st.session_state.get("messages", []):
            api_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        api_messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages,
            max_tokens=4000,
            temperature=0.6
        )
        
        reply = response.choices[0].message.content
        
        if reply:
            parse_ai_response(reply)
            return reply
        else:
            return "I could not generate a response. Please try again."
            
    except Exception as e:
        err = str(e)
        if "401" in err:
            return "ERROR: Invalid API key. Check your secrets."
        elif "429" in err:
            return "ERROR: Rate limited. Wait a moment."
        elif "404" in err:
            return "ERROR: Model not found. The model name may be wrong."
        else:
            return "ERROR: " + err[:100]

# ============ HEADER ============
st.markdown("""
<div class="app-header">
    <h1>Studio.</h1>
    <p>Topology Optimization and System Design</p>
</div>
""", unsafe_allow_html=True)

# ============ WELCOME BACK ============
if len(st.session_state.get("messages", [])) > 0:
    count = len(st.session_state.messages)
    st.markdown(
        f'<div style="background:#0A84FF15;border:1px solid #0A84FF30;border-radius:10px;padding:0.5rem 1rem;text-align:center;margin:0.5rem 0;"><p style="color:#7DD3FC;font-size:0.8125rem;margin:0;">Welcome back - {count} messages saved</p></div>',
        unsafe_allow_html=True
    )

# ============ START SCREEN ============
if len(st.session_state.get("messages", [])) == 0:

    st.write("")
    
    # Show API key status
    if API_KEY:
        st.markdown(
            '<p style="color:#30D158;font-size:0.75rem;text-align:center;">API key found - ready to start</p>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<p style="color:#FF453A;font-size:0.75rem;text-align:center;">No API key found - add STEPFUN_API_KEY in Secrets</p>',
            unsafe_allow_html=True
        )
    
    st.write("")
    
    # Topology Optimization card
    st.markdown("""
    <div class="project-card">
        <h3>Topology Optimization</h3>
        <p>Build a structural optimization solver with visual demos</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Start Topology Optimization", use_container_width=True, type="primary"):
        st.session_state.start_requested = "topology"
    
    st.write("")
    
    # System Design card
    st.markdown("""
    <div class="project-card">
        <h3>System Design</h3>
        <p>Design real systems with architecture and code</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Start System Design", use_container_width=True, type="primary"):
        st.session_state.start_requested = "system_design"

# ============ HANDLE START ============
if st.session_state.get("start_requested"):
    track = st.session_state.start_requested
    st.session_state.start_requested = None
    
    st.session_state.current_track = track
    
    if track == "topology":
        first_msg = "I want to start learning Topology Optimization from the very beginning. I need everything shown visually."
    else:
        first_msg = "I want to start learning System Design from the very beginning. I need everything shown visually."
    
    # Add user message
    st.session_state.messages = [{"role": "user", "content": first_msg}]
    
    # Show loading
    with st.chat_message("assistant"):
        with st.spinner("Starting your project..."):
            # Call API
            response = call_api(first_msg)
    
    # Add AI response
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Save
    save_history()
    
    # Force page refresh to show conversation
    st.rerun()

# ============ DISPLAY CHAT ============
for message in st.session_state.get("messages", []):
    role = message.get("role", "user")
    content = message.get("content", "")
    clean = safe_clean(content)
    
    if not clean:
        continue
    
    if role == "user":
        _, col = st.columns([0.35, 0.65])
        with col:
            with st.chat_message("user"):
                st.write(clean)
    else:
        col, _ = st.columns([0.8, 0.2])
        with col:
            with st.chat_message("assistant"):
                st.write(clean)

# ============ CODE SANDBOX ============
if st.session_state.get("show_code_editor", False):
    
    st.markdown('<div class="section-label">Practice</div>', unsafe_allow_html=True)
    
    exercise = st.session_state.get("code_exercise", "")
    if exercise:
        st.info("Task: " + exercise)
    
    code = st.text_area(
        "Code",
        value=st.session_state.get("code_content", "# Type your code here"),
        height=180,
        key="code_field",
        label_visibility="collapsed"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Run Code", use_container_width=True, type="primary"):
            st.session_state.code_content = code
            with st.spinner("Running..."):
                output, error, has_fig, fig = execute_code(code)
                st.session_state.code_output = output or ""
                st.session_state.code_error = error or ""
                st.session_state.code_ran = True
                st.session_state.has_plot = has_fig
                st.session_state.current_plot = fig
    
    with col2:
        if st.button("Submit to Mentor", use_container_width=True):
            if not st.session_state.get("code_ran", False):
                st.warning("Run your code first.")
            else:
                submission = "I completed the exercise.\n\nMy code:\n"
                submission += "```python\n" + code + "\n```\n\n"
                
                out = st.session_state.get("code_output", "")
                err = st.session_state.get("code_error", "")
                
                if out:
                    submission += "Output:\n```\n" + out + "\n```\n"
                if err and "Traceback" in err:
                    submission += "I got an error:\n```\n" + err + "\n```"
                else:
                    submission += "Please review my work."
                
                st.session_state.messages.append({"role": "user", "content": submission})
                st.session_state.show_code_editor = False
                
                with st.spinner("Mentor is reviewing..."):
                    response = call_api(submission)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_history()
                st.rerun()
    
    if st.session_state.get("code_ran", False):
        out = st.session_state.get("code_output", "")
        err = st.session_state.get("code_error", "")
        
        if out:
            st.markdown('<div class="output-box">' + out + '</div>', unsafe_allow_html=True)
        if err and "Traceback" in err:
            lines = err.split("\n")
            clean_err = "\n".join(lines[-5:])
            st.markdown('<div class="error-box">' + clean_err + '</div>', unsafe_allow_html=True)

# ============ VISUALIZATION ============
if st.session_state.get("has_plot", False):
    fig = st.session_state.get("current_plot", None)
    if fig is not None:
        st.markdown('<div class="section-label">Visualization</div>', unsafe_allow_html=True)
        try:
            st.pyplot(fig, use_container_width=True)
        except:
            st.caption("Run the code again to see the plot.")
        st.write("")

# ============ QUIZ ============
if st.session_state.get("show_quiz", False):
    st.markdown('<div class="section-label">Quick Check</div>', unsafe_allow_html=True)
    question = st.session_state.get("quiz_question", "")
    if question:
        st.write("**" + question + "**")
    st.write("")
    
    options = st.session_state.get("quiz_options", [])
    for i, option in enumerate(options):
        if st.button(option, key="quiz_" + str(i), use_container_width=True):
            st.session_state.show_quiz = False
            answer = "My answer: " + option
            st.session_state.messages.append({"role": "user", "content": answer})
            
            with st.spinner("Checking..."):
                response = call_api(answer)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_history()
            st.rerun()

# ============ CHAT INPUT ============
if prompt := st.chat_input("Type your message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    _, col = st.columns([0.35, 0.65])
    with col:
        with st.chat_message("user"):
            st.write(prompt)
    
    col, _ = st.columns([0.8, 0.2])
    with col:
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = call_api(prompt)
            st.write(safe_clean(response))
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_history()

# ============ FOOTER ============
st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    if st.button("Reset", use_container_width=True):
        clear_all()
        st.rerun()

st.markdown(
    '<div style="text-align:center;color:#3A3A3C;font-size:0.6875rem;padding:0.25rem 0;">Auto-saved</div>',
    unsafe_allow_html=True
)
