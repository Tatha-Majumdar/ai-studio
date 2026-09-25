import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import time
import re
import json

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"
HISTORY_FILE = "chat_history.json"

# ============ SESSION STATE ============
DEFAULTS = {
    "messages": [],
    "concepts_learned": [],
    "exercises_completed": 0,
    "current_track": None,
    "show_code_editor": False,
    "code_exercise": "",
    "code_content": "# Type your code here\n",
    "code_output": "",
    "code_error": "",
    "code_ran": False,
    "current_plot": None,
    "has_plot": False,
    "show_quiz": False,
    "quiz_question": "",
    "quiz_options": [],
    "loaded": False,
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ============ PERSISTENCE ============
def save_history():
    try:
        data = {
            "messages": st.session_state.get("messages", []),
            "concepts_learned": st.session_state.get("concepts_learned", []),
            "exercises_completed": st.session_state.get("exercises_completed", 0),
            "current_track": st.session_state.get("current_track"),
            "show_code_editor": st.session_state.get("show_code_editor", False),
            "code_exercise": st.session_state.get("code_exercise", ""),
            "code_content": st.session_state.get("code_content", ""),
            "code_output": st.session_state.get("code_output", ""),
            "code_error": st.session_state.get("code_error", ""),
            "code_ran": st.session_state.get("code_ran", False),
            "has_plot": st.session_state.get("has_plot", False),
        }
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass

def load_history():
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in st.session_state:
                    st.session_state[key] = value
            st.session_state["current_plot"] = None
            st.session_state["has_plot"] = False
            return True
    except Exception:
        pass
    return False

if not st.session_state.get("loaded", False):
    load_history()
    st.session_state["loaded"] = True

def clear_all():
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass
    for key, default in DEFAULTS.items():
        st.session_state[key] = default

# ============ API KEY ============
API_KEY = ""
try:
    API_KEY = st.secrets.get("STEPFUN_API_KEY", "")
except Exception:
    pass
if not API_KEY:
    API_KEY = os.environ.get("STEPFUN_API_KEY", "")

# ============ MENTOR PROMPT (Simplified, ASCII-only) ============
MENTOR_PROMPT = (
    "You are a senior engineering mentor teaching two subjects: "
    "Topology Optimization and System Design. "
    "The student may have zero coding experience.\n\n"
    "CRITICAL RULE: The student CANNOT imagine or visualize things mentally. "
    "NEVER say 'imagine', 'picture', 'visualize', or 'think about'. "
    "Instead, ALWAYS provide one of these:\n"
    "- Matplotlib code that draws the concept\n"
    "- Printed output showing real data\n"
    "- A concrete example with actual numbers\n"
    "- ASCII art diagram\n"
    "- Runnable code that demonstrates the idea\n\n"
    "BAD: 'Imagine a beam fixed at one end.'\n"
    "GOOD: 'Run this code to see a beam:' then provide matplotlib code.\n\n"
    "PLATFORM MARKERS:\n"
    "End message with [PRACTICE] followed by a coding exercise to show an editor.\n"
    "Use [QUIZ] Question | Option A | Option B | Option C for quizzes.\n\n"
    "TEACHING RULES:\n"
    "- One concept at a time, never overwhelm\n"
    "- Always show a visual or concrete example\n"
    "- Code examples must run and produce visible output\n"
    "- Keep messages under 200 words\n"
    "- When reviewing student code: what works, what to fix\n"
    "- Track what was taught and reference it later\n"
    "- If student returns, recap and continue from where they left off\n\n"
    "APPROACH:\n"
    "- Project-driven: every concept serves the final project\n"
    "- For Topology Optimization: build a SIMP solver, teach Python as needed\n"
    "- For System Design: build real systems, teach coding as needed\n"
    "- Start from absolute zero if student has no experience\n\n"
    "FIRST INTERACTION: Ask about coding experience, then start lesson 1."
)

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============ CSS ============
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

.stApp {
    background: #0A0A0A;
    font-family: 'Inter', -apple-system, sans-serif;
    color: #F5F5F5;
}

#MainMenu, footer, header, [data-testid="stSidebar"], [data-testid="stToolbar"] {
    display: none !important;
}

.block-container {
    padding-top: 1rem;
    padding-bottom: 0;
    max-width: 720px;
}

.app-header {
    text-align: center;
    padding: 1rem 0 0.75rem 0;
    border-bottom: 1px solid #1A1A1A;
    margin-bottom: 0.5rem;
}

.app-header h1 {
    font-size: 1.75rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: #F5F5F5;
    margin: 0;
}

.app-header p {
    font-size: 0.8125rem;
    color: #6E6E73;
    margin: 0.25rem 0 0 0;
}

.welcome-back {
    background: #0A84FF15;
    border: 1px solid #0A84FF30;
    border-radius: 10px;
    padding: 0.5rem 1rem;
    margin: 0.5rem 0;
    text-align: center;
}

.welcome-back p {
    color: #7DD3FC;
    font-size: 0.8125rem;
    margin: 0;
}

[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: 0.25rem 0 !important;
    margin: 0 !important;
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
    font-size: 0.85em;
}

[data-testid="stChatMessage"] pre code {
    background: transparent;
    padding: 0;
    color: inherit;
}

[data-testid="stChatMessage"] strong {
    color: #FFFFFF;
    font-weight: 600;
}

[data-testid="stChatMessage"] ul { padding-left: 1.25rem; }
[data-testid="stChatMessage"] li { color: #D0D0D0; }

[data-testid="stChatInput"] textarea {
    background: #141414 !important;
    border: 1px solid #2A2A2A !important;
    border-radius: 18px !important;
    color: #F5F5F5 !important;
    font-size: 0.9375rem !important;
    font-family: 'Inter', sans-serif !important;
    padding: 0.75rem 1.125rem !important;
}

[data-testid="stChatInput"] textarea:focus {
    border-color: #0A84FF !important;
}

.stTextArea textarea {
    background: #0A0A0A !important;
    border: 1px solid #1E1E1E !important;
    border-radius: 12px !important;
    font-family: monospace !important;
    color: #E0E0E0 !important;
    font-size: 0.875rem !important;
    padding: 1rem !important;
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
    padding: 1.25rem;
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
    line-height: 1.5;
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

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0A0A0A; }
::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 3px; }
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
    if not code or not isinstance(code, str):
        return "", "No code provided", False, None
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
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
        with contextlib.redirect_stdout(stdout_capture):
            with contextlib.redirect_stderr(stderr_capture):
                exec(code, namespace)
        
        output = stdout_capture.getvalue()
        error = stderr_capture.getvalue()
        
        has_figure = False
        figure = None
        try:
            if 'plt' in namespace:
                nums = plt.get_fignums()
                if nums:
                    has_figure = True
                    figure = plt.figure(nums[0])
        except:
            pass
        
        return output, error, has_figure, figure
        
    except Exception:
        output = stdout_capture.getvalue()
        error = traceback.format_exc()
        return output, error, False, None
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def get_ai_response(user_message, placeholder=None):
    if not API_KEY:
        msg = "Setup needed. Add your API key in Streamlit Cloud Settings, Secrets section."
        if placeholder:
            placeholder.markdown(msg)
        return msg
    
    try:
        client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        
        for msg in st.session_state.get("messages", []):
            try:
                api_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            except:
                pass
        
        api_messages.append({"role": "user", "content": user_message})
        
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages,
            stream=True,
            max_tokens=4000,
            temperature=0.6
        )
        
        full_response = ""
        
        if placeholder:
            for chunk in stream:
                try:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        clean = safe_clean(full_response)
                        placeholder.markdown(clean + "|")
                except:
                    pass
            clean = safe_clean(full_response)
            placeholder.markdown(clean)
        else:
            for chunk in stream:
                try:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                except:
                    pass
        
        parse_ai_response(full_response)
        save_history()
        
        return full_response if full_response else "Could you rephrase that?"
        
    except Exception as e:
        error_str = str(e)
        if "401" in error_str:
            msg = "Invalid API key. Check your Streamlit secrets."
        elif "429" in error_str:
            msg = "Rate limit. Wait a moment and try again."
        else:
            msg = "Connection error. Please try again."
        
        if placeholder:
            placeholder.markdown(msg)
        return msg

def render_msg(role, content):
    clean = safe_clean(content)
    if not clean:
        return
    
    try:
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
    except:
        with st.chat_message(role):
            st.write(clean)

# ============ MAIN APP ============

st.markdown("""
<div class="app-header">
    <h1>Studio.</h1>
    <p>Topology Optimization and System Design</p>
</div>
""", unsafe_allow_html=True)

try:
    msg_count = len(st.session_state.get("messages", []))
    if msg_count > 0:
        st.markdown(
            '<div class="welcome-back"><p>Welcome back - '
            + str(msg_count)
            + ' messages saved</p></div>',
            unsafe_allow_html=True
        )
except:
    pass

# ============ TRACK SELECTION ============
try:
    if len(st.session_state.get("messages", [])) == 0:
        st.write("")
        
        st.markdown("""
        <div class="project-card">
            <h3>Topology Optimization</h3>
            <p>Build a structural optimization solver. Everything shown visually with code.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Start Topology Optimization", use_container_width=True, type="primary"):
            st.session_state.current_track = "topology"
            msg = "I want to start Topology Optimization. Show everything visually. Start from the beginning."
            st.session_state.messages = [{"role": "user", "content": msg}]
            
            with st.chat_message("assistant"):
                ph = st.empty()
                response = get_ai_response(msg, ph)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_history()
            st.rerun()
        
        st.write("")
        
        st.markdown("""
        <div class="project-card">
            <h3>System Design</h3>
            <p>Design and build real systems. Architecture with working code.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Start System Design", use_container_width=True, type="primary"):
            st.session_state.current_track = "system_design"
            msg = "I want to start System Design. Show everything visually. Start from the beginning."
            st.session_state.messages = [{"role": "user", "content": msg}]
            
            with st.chat_message("assistant"):
                ph = st.empty()
                response = get_ai_response(msg, ph)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_history()
            st.rerun()
        
        st.write("")
        st.caption("Progress auto-saved. Refresh anytime.")
except Exception:
    pass

# ============ CHAT HISTORY ============
try:
    for message in st.session_state.get("messages", []):
        render_msg(message.get("role", "user"), message.get("content", ""))
except Exception:
    pass

# ============ CODE SANDBOX ============
try:
    if st.session_state.get("show_code_editor", False):
        
        st.markdown('<div class="section-label">Practice</div>', unsafe_allow_html=True)
        
        exercise = st.session_state.get("code_exercise", "")
        if exercise:
            st.info("Task: " + exercise)
        
        code = st.text_area(
            "",
            value=st.session_state.get("code_content", "# Type your code here"),
            height=180,
            key="code_editor_field",
            label_visibility="collapsed"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Run", use_container_width=True, type="primary"):
                st.session_state.code_content = code
                with st.spinner("Running..."):
                    try:
                        output, error, has_fig, fig = execute_code(code)
                        st.session_state.code_output = output or ""
                        st.session_state.code_error = error or ""
                        st.session_state.code_ran = True
                        st.session_state.has_plot = has_fig
                        st.session_state.current_plot = fig
                        save_history()
                    except Exception as e:
                        st.session_state.code_output = ""
                        st.session_state.code_error = str(e)
                        st.session_state.code_ran = True
        
        with col2:
            if st.button("Submit", use_container_width=True):
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
                        submission += "Error - help me fix:\n```\n" + err + "\n```"
                    else:
                        submission += "Please review my work."
                    
                    st.session_state.messages.append({"role": "user", "content": submission})
                    st.session_state.exercises_completed += 1
                    st.session_state.show_code_editor = False
                    
                    with st.chat_message("assistant"):
                        ph = st.empty()
                        response = get_ai_response(submission, ph)
                    
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
                clean_err = "\n".join(lines[-5:]) if len(lines) > 5 else err
                st.markdown('<div class="error-box">' + clean_err + '</div>', unsafe_allow_html=True)
except Exception:
    pass

# ============ VISUALIZATION ============
try:
    if st.session_state.get("has_plot", False):
        fig = st.session_state.get("current_plot", None)
        if fig is not None:
            st.markdown('<div class="section-label">Visualization</div>', unsafe_allow_html=True)
            try:
                st.pyplot(fig, use_container_width=True)
            except:
                st.caption("Run the code again to see the plot.")
            st.write("")
except Exception:
    pass

# ============ QUIZ ============
try:
    if st.session_state.get("show_quiz", False):
        st.markdown('<div class="section-label">Quick Check</div>', unsafe_allow_html=True)
        question = st.session_state.get("quiz_question", "")
        if question:
            st.write("**" + question + "**")
        st.write("")
        
        options = st.session_state.get("quiz_options", [])
        for i, option in enumerate(options):
            if st.button(option, key="quiz_opt_" + str(i), use_container_width=True):
                st.session_state.show_quiz = False
                answer = "My answer: " + option
                st.session_state.messages.append({"role": "user", "content": answer})
                
                with st.chat_message("assistant"):
                    ph = st.empty()
                    response = get_ai_response(answer, ph)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_history()
                st.rerun()
except Exception:
    pass

# ============ CHAT INPUT ============
try:
    if prompt := st.chat_input("Type here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        _, col = st.columns([0.35, 0.65])
        with col:
            with st.chat_message("user"):
                st.write(prompt)
        
        col, _ = st.columns([0.8, 0.2])
        with col:
            with st.chat_message("assistant"):
                ph = st.empty()
                response = get_ai_response(prompt, ph)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_history()
        st.rerun()
except Exception:
    pass

# ============ FOOTER ============
st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    if st.button("Reset", use_container_width=True):
        clear_all()
        st.rerun()

st.markdown(
    '<div style="text-align:center;padding:0.25rem 0;color:#3A3A3C;font-size:0.6875rem;">Auto-saved</div>',
    unsafe_allow_html=True
)
