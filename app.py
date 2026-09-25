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
    "visual_plots": [],  # Store executed figures
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

# ============ MENTOR PROMPT (FIXED) ============
MENTOR_PROMPT = (
    "You are a senior engineering mentor teaching Topology Optimization and System Design. "
    "The student may have zero coding experience.\n\n"
    
    "CRITICAL INTERACTION RULES - FOLLOW THESE EXACTLY:\n"
    "1. ASK ONE QUESTION AT A TIME. When you ask a question, STOP. End your message. "
    "Do NOT continue to the next lesson. WAIT for the student to respond first.\n"
    "2. ONE MESSAGE = ONE PURPOSE. Either ask a question, OR give a lesson, OR show a visual. "
    "NEVER combine asking a question with giving a lesson in the same message.\n"
    "3. When the student answers your question, THEN give the next lesson.\n\n"
    
    "VISUALIZATION RULES:\n"
    "4. NEVER paste matplotlib code as plain text in your message. The student cannot run it there.\n"
    "5. When you want to SHOW a visualization (plot, diagram, structure), use this format:\n"
    "   [VISUAL]\n"
    "   <python code that creates the plot>\n"
    "   [/VISUAL]\n"
    "   The platform will execute this code and display the image to the student.\n"
    "6. When you want the STUDENT to write code, use:\n"
    "   [PRACTICE] <exercise description>\n"
    "7. Use [VISUAL] for showing concepts. Use [PRACTICE] for exercises.\n\n"
    
    "NO IMAGINING RULE:\n"
    "8. Never say imagine, picture, or visualize. The student must SEE everything.\n"
    "9. Every concept must be shown with a [VISUAL] block or concrete code output.\n\n"
    
    "TEACHING FLOW:\n"
    "Step 1: Ask about coding experience. WAIT for answer.\n"
    "Step 2: Based on answer, start Lesson 1 with a [VISUAL] showing the concept.\n"
    "Step 3: Explain what the visual shows.\n"
    "Step 4: [PRACTICE] exercise for the student.\n"
    "Step 5: Review their work when submitted.\n"
    "Step 6: Continue to next concept.\n\n"
    
    "STYLE: Under 200 words per message. Track what was taught. "
    "Reference previous lessons. Be encouraging but rigorous."
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');

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
    font-family: 'JetBrains Mono', monospace;
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

.visual-block {
    background: #141414;
    border: 1px solid #0A84FF30;
    border-radius: 12px;
    padding: 0.5rem;
    margin: 0.75rem 0;
}

.visual-label {
    font-size: 0.6875rem;
    font-weight: 700;
    color: #0A84FF;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
    padding-left: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

# ============ HELPER FUNCTIONS ============
def safe_clean(text):
    if not text or not isinstance(text, str):
        return ""
    try:
        # Remove [VISUAL]...[/VISUAL] blocks
        clean = re.sub(r'\[VISUAL\].*?\[/VISUAL\]', '[VISUALIZATION SHOWN ABOVE]', text, flags=re.DOTALL)
        clean = re.sub(r'\[PRACTICE\].*', '', clean, flags=re.DOTALL)
        clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
        return clean.strip()
    except:
        return str(text) if text else ""

def extract_visual_code(text):
    """Extract matplotlib code from [VISUAL]...[/VISUAL] blocks."""
    if not text or not isinstance(text, str):
        return []
    
    codes = []
    pattern = r'\[VISUAL\]\s*(.*?)\s*\[/VISUAL\]'
    matches = re.findall(pattern, text, flags=re.DOTALL)
    
    for match in matches:
        # Clean up the code
        code = match.strip()
        if code.startswith('```python'):
            code = code[9:]
        if code.startswith('```'):
            code = code[3:]
        if code.endswith('```'):
            code = code[:-3]
        code = code.strip()
        if code:
            codes.append(code)
    
    return codes

def parse_ai_response(text):
    """Parse AI markers."""
    if not text or not isinstance(text, str):
        return
    
    # [PRACTICE] marker
    try:
        if "[PRACTICE]" in text:
            match = re.search(r'\[PRACTICE\]\s*(.+)', text, re.DOTALL)
            if match:
                # Remove any [VISUAL] blocks from the exercise
                exercise = match.group(1).strip()
                exercise = re.sub(r'\[VISUAL\].*?\[/VISUAL\]', '', exercise, flags=re.DOTALL).strip()
                st.session_state.show_code_editor = True
                st.session_state.code_exercise = exercise
                st.session_state.code_ran = False
                st.session_state.code_output = ""
                st.session_state.code_error = ""
    except:
        pass
    
    # [QUIZ] marker
    try:
        if "[QUIZ]" in text:
            parts = text.split("[QUIZ]")[1].split("|")
            if len(parts) >= 2:
                st.session_state.show_quiz = True
                st.session_state.quiz_question = parts[0].strip()
                st.session_state.quiz_options = [p.strip() for p in parts[1:] if p.strip()]
    except:
        pass

def execute_visual_code(code):
    """Execute matplotlib code and return the figure."""
    if not code:
        return None
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_cap = io.StringIO()
    stderr_cap = io.StringIO()
    
    namespace = {"__name__": "__main__"}
    
    # Import matplotlib
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        namespace['plt'] = plt
    except:
        return None
    
    # Import numpy
    try:
        import numpy as np
        namespace['np'] = np
    except:
        pass
    
    try:
        with contextlib.redirect_stdout(stdout_cap):
            with contextlib.redirect_stderr(stderr_cap):
                exec(code, namespace)
        
        # Get the figure
        nums = plt.get_fignums()
        if nums:
            fig = plt.figure(nums[0])
            plt.close('all')  # Clear for next time
            return fig
        return None
        
    except Exception:
        return None
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

def execute_code(code):
    """Execute code for practice exercises."""
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
            nums = plt.get_fignums()
            if nums:
                has_fig = True
                fig = plt.figure(nums[0])
                plt.close('all')
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
    """Simple API call. Returns response text."""
    
    if not API_KEY:
        return "ERROR: No API key found. Add STEPFUN_API_KEY in Streamlit Cloud Secrets."
    
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
            return "ERROR: Invalid API key."
        elif "429" in err:
            return "ERROR: Rate limited. Wait a moment."
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
        f'<div style="background:#0A84FF15;border:1px solid #0A84FF30;border-radius:10px;padding:0.5rem 1rem;text-align:center;margin:0.5rem 0;"><p style="color:#7DD3FC;font-size:0.8125rem;margin:0;">Welcome back - {count} messages</p></div>',
        unsafe_allow_html=True
    )

# ============ START SCREEN ============
if len(st.session_state.get("messages", [])) == 0:

    st.write("")
    
    if API_KEY:
        st.markdown(
            '<p style="color:#30D158;font-size:0.75rem;text-align:center;">Ready to start</p>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<p style="color:#FF453A;font-size:0.75rem;text-align:center;">No API key - add in Secrets</p>',
            unsafe_allow_html=True
        )
    
    st.write("")
    
    st.markdown("""
    <div class="project-card">
        <h3>Topology Optimization</h3>
        <p>Build a structural optimization solver with visual demos</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Start Topology Optimization", use_container_width=True, type="primary"):
        st.session_state.start_requested = "topology"
    
    st.write("")
    
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
        first_msg = "I want to start Topology Optimization from the very beginning."
    else:
        first_msg = "I want to start System Design from the very beginning."
    
    st.session_state.messages = [{"role": "user", "content": first_msg}]
    
    with st.spinner("Starting..."):
        response = call_api(first_msg)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_history()
    st.rerun()

# ============ DISPLAY CHAT (WITH VISUALS) ============
for message in st.session_state.get("messages", []):
    role = message.get("role", "user")
    content = message.get("content", "")
    
    if not content:
        continue
    
    # For user messages - right aligned
    if role == "user":
        clean = safe_clean(content)
        if clean:
            _, col = st.columns([0.35, 0.65])
            with col:
                with st.chat_message("user"):
                    st.write(clean)
    
    # For assistant messages - left aligned, with visuals
    else:
        # Check for [VISUAL] blocks
        visual_codes = extract_visual_code(content)
        
        if visual_codes:
            # Split message into text and visual parts
            # Display text part
            clean = safe_clean(content)
            col, _ = st.columns([0.8, 0.2])
            with col:
                with st.chat_message("assistant"):
                    st.write(clean)
            
            # Display visualizations
            for code in visual_codes:
                st.markdown('<div class="visual-block"><div class="visual-label">Visualization</div>', unsafe_allow_html=True)
                fig = execute_visual_code(code)
                if fig is not None:
                    st.pyplot(fig, use_container_width=True)
                else:
                    st.caption("Visualization unavailable")
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            # No visuals - just text
            clean = safe_clean(content)
            if clean:
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
                
                with st.spinner("Reviewing..."):
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
if prompt := st.chat_input("Type your answer or question..."):
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
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_history()
    st.rerun()

# ============ FOOTER ============
st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    if st.button("Reset", use_container_width=True):
        clear_all()
        st.rerun()
