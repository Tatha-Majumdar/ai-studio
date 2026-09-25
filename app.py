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

# ============ PERSISTENCE FUNCTIONS ============
def save_history():
    """Save all session state to file so it survives page refresh."""
    data = {
        "messages": st.session_state.messages,
        "concepts_learned": st.session_state.concepts_learned,
        "exercises_completed": st.session_state.exercises_completed,
        "current_track": st.session_state.current_track,
        "show_code_editor": st.session_state.show_code_editor,
        "code_exercise": st.session_state.code_exercise,
        "code_content": st.session_state.code_content,
        "code_output": st.session_state.code_output,
        "code_error": st.session_state.code_error,
        "code_ran": st.session_state.code_ran,
        "has_plot": st.session_state.has_plot,
    }
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except:
        pass  # Silently fail if file system isn't writable

def load_history():
    """Load saved state from file if it exists."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
            
            st.session_state.messages = data.get("messages", [])
            st.session_state.concepts_learned = data.get("concepts_learned", [])
            st.session_state.exercises_completed = data.get("exercises_completed", 0)
            st.session_state.current_track = data.get("current_track", None)
            st.session_state.show_code_editor = data.get("show_code_editor", False)
            st.session_state.code_exercise = data.get("code_exercise", "")
            st.session_state.code_content = data.get("code_content", "# Type your code here\n")
            st.session_state.code_output = data.get("code_output", "")
            st.session_state.code_error = data.get("code_error", "")
            st.session_state.code_ran = data.get("code_ran", False)
            st.session_state.has_plot = data.get("has_plot", False)
            return True
    except:
        pass
    return False

def clear_history():
    """Clear all saved state."""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except:
        pass
    
    # Reset session state
    st.session_state.messages = []
    st.session_state.concepts_learned = []
    st.session_state.exercises_completed = 0
    st.session_state.current_track = None
    st.session_state.show_code_editor = False
    st.session_state.code_exercise = ""
    st.session_state.code_content = "# Type your code here\n"
    st.session_state.code_output = ""
    st.session_state.code_error = ""
    st.session_state.code_ran = False
    st.session_state.has_plot = False
    st.session_state.current_plot = None
    st.session_state.show_quiz = False

# ============ SESSION STATE ============
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.concepts_learned = []
    st.session_state.exercises_completed = 0
    st.session_state.current_track = None
    st.session_state.show_code_editor = False
    st.session_state.code_exercise = ""
    st.session_state.code_content = "# Type your code here\n"
    st.session_state.code_output = ""
    st.session_state.code_error = ""
    st.session_state.code_ran = False
    st.session_state.current_plot = None
    st.session_state.has_plot = False
    st.session_state.show_quiz = False
    st.session_state.quiz_question = ""
    st.session_state.quiz_options = []
    
    # Try to load saved history
    load_history()

# ============ API KEY ============
API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))

# ============ MENTOR BRAIN ============
MENTOR_PROMPT = """
You are a senior engineering mentor inside an interactive learning platform. You teach exactly two subjects:

1. **Topology Optimization** — structural engineering, SIMP method, FEA, Python/NumPy
2. **System Design** — software architecture, scalability, real systems

Your student may have ZERO coding experience. You teach everything needed — coding, math, engineering — but always in service of these two projects.

## CONTROLLING THE PLATFORM

You control what the student sees. Use these markers:

**[PRACTICE]** — Shows a code editor. End your message with:
[PRACTICE] Write code that...

**[QUIZ]** — Shows interactive quiz. Format:
[QUIZ] Question | Option A | Option B | Option C

Use markers only when the student needs to practice or you need to check understanding. Otherwise just explain.

## SESSION CONTINUITY — CRITICAL

You MUST maintain continuity across sessions. When the student returns:
- If they say "continue" or similar, review the conversation history
- Identify what was last taught
- Summarize: "Last time we covered X. Ready to continue with Y?"
- Then pick up exactly where you left off

Never re-teach something already covered. Reference previous lessons.

## TEACHING APPROACH — PROJECT-DRIVEN

Every concept is learned because the project needs it. You never teach in the abstract.

### For Topology Optimization:
- Start: What is topology optimization? Why do engineers use it?
- Then: Basic Python (print, variables) — needed for the solver
- Then: NumPy arrays — needed for the mesh
- Then: Loops and functions — needed for the optimization algorithm
- Then: Matplotlib — needed to visualize structures
- Then: The actual SIMP method and FEA concepts
- Final: A complete working topology optimization solver

### For System Design:
- Start: What is system design? Why does it matter?
- Then: Basic coding (in whatever language needed)
- Then: Requirements gathering and scope
- Then: Architecture patterns and trade-offs
- Then: Building actual components
- Final: A complete system design with working code

## WHEN STUDENT RETURNS AFTER REFRESH

If the conversation history shows previous messages:
1. Acknowledge their return warmly
2. Briefly recap what was covered
3. Ask if they want to continue or review
4. Then proceed with the next concept

Example: "Welcome back! Last session we covered variables and printing. Ready to learn about lists, which we'll need for storing our mesh data?"

## TEACHING STYLE
- One concept at a time — never overwhelm
- Explain WHY before HOW
- Use analogies from physics/engineering for TopOpt
- Use analogies from everyday systems for System Design
- After every concept: [PRACTICE] exercise
- Review their code: what's correct, what to fix
- If they struggle: simplify, don't skip
- Track all concepts taught and reference them later
- Keep responses under 200 words when possible

## FIRST INTERACTION

When the student selects a track, greet them:
- For Topology Optimization: "Welcome! We're going to build a real topology optimization solver — the same type of tool engineers at companies like Altair and Siemens use. I'll teach you everything you need, starting from absolute basics. First question: have you ever written any code before?"
- For System Design: "Welcome! We're going to learn how to design and build real software systems — the skills senior engineers use at companies like Google and Netflix. I'll teach you everything from scratch. First: have you written any code before?"
"""

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio — Learn Engineering",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============ APPLE HIG DARK MODE CSS ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    .stApp {
        background: #0A0A0A;
        color: #F5F5F5;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
    }

    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }

    .block-container {
        padding-top: 0;
        padding-bottom: 0;
        max-width: 720px;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Header */
    .app-header {
        text-align: center;
        padding: 2rem 0 1.5rem 0;
        border-bottom: 1px solid #1A1A1A;
    }

    .app-header h1 {
        font-size: 2.25rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        color: #F5F5F5;
        margin: 0;
    }

    .app-header p {
        font-size: 0.875rem;
        color: #6E6E73;
        margin-top: 0.375rem;
    }

    /* Welcome back banner */
    .welcome-back {
        background: linear-gradient(135deg, #0A84FF10, #0A84FF05);
        border: 1px solid #0A84FF30;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
        text-align: center;
    }

    .welcome-back p {
        color: #7DD3FC;
        font-size: 0.875rem;
        margin: 0;
    }

    /* Project cards */
    .project-card {
        background: #141414;
        border: 1px solid #262626;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 0.75rem 0;
        transition: all 0.2s;
        cursor: pointer;
    }

    .project-card:hover {
        border-color: #0A84FF;
        background: #1A1A1A;
    }

    .project-card h3 {
        color: #F5F5F5;
        font-size: 1.125rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.02em;
    }

    .project-card p {
        color: #8E8E93;
        font-size: 0.875rem;
        margin: 0;
        line-height: 1.5;
    }

    .project-card .tag {
        display: inline-block;
        font-size: 0.6875rem;
        font-weight: 600;
        color: #0A84FF;
        background: #0A84FF15;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        margin-top: 0.75rem;
    }

    /* Chat */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.375rem 0;
    }

    [data-testid="stChatMessageContent"] {
        font-size: 0.9375rem;
        line-height: 1.7;
        color: #F5F5F5;
    }

    [data-testid="stChatMessage"] pre {
        background: #141414;
        border: 1px solid #262626;
        border-radius: 10px;
        padding: 1rem;
        font-size: 0.8125rem;
        font-family: 'JetBrains Mono', monospace;
        color: #E0E0E0;
    }

    [data-testid="stChatMessage"] code {
        background: #1E1E1E;
        color: #7DD3FC;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
    }

    /* Chat input */
    [data-testid="stChatInput"] textarea {
        background: #141414 !important;
        border: 1px solid #2A2A2A !important;
        border-radius: 18px !important;
        color: #F5F5F5 !important;
        font-size: 0.9375rem !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.75rem 1.25rem !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: #0A84FF !important;
        background: #1A1A1A !important;
    }

    /* Code editor */
    .stTextArea textarea {
        background: #0A0A0A !important;
        border: 1px solid #1E1E1E !important;
        border-radius: 12px !important;
        font-family: 'JetBrains Mono', monospace !important;
        color: #E0E0E0 !important;
        font-size: 0.875rem !important;
        line-height: 1.7 !important;
        padding: 1rem !important;
    }

    /* Buttons */
    .stButton > button {
        background: #0A84FF;
        color: #FFFFFF;
        border: none;
        border-radius: 12px;
        padding: 0.625rem 1.5rem;
        font-weight: 600;
        font-size: 0.875rem;
        font-family: 'Inter', sans-serif;
    }

    .stButton > button:hover {
        background: #409CFF;
    }

    /* Output */
    .output-box {
        background: #0D0D0D;
        border: 1px solid #30D15830;
        border-radius: 10px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        color: #30D158;
        white-space: pre-wrap;
        margin: 0.5rem 0;
    }

    .error-box {
        background: #1A0D0D;
        border: 1px solid #FF453A30;
        border-radius: 10px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        color: #FF453A;
        white-space: pre-wrap;
        margin: 0.5rem 0;
    }

    /* Progress */
    .progress-info {
        background: #141414;
        border: 1px solid #262626;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 1rem 0;
        font-size: 0.8125rem;
        color: #6E6E73;
    }

    .progress-info .stat {
        color: #0A84FF;
        font-weight: 600;
    }

    /* Section label */
    .section-label {
        font-size: 0.6875rem;
        font-weight: 700;
        color: #0A84FF;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 1.25rem 0 0.5rem 0;
    }

    /* Misc */
    hr { border: none; height: 1px; background: #1A1A1A; margin: 1.5rem 0; }
    .stCaption { color: #3A3A3C; }
    
    [data-testid="stInfo"] {
        background: #0D0D0D;
        border: 1px solid #0A84FF;
        border-radius: 10px;
        color: #A0C4FF;
    }

    [data-testid="stSpinner"] > div {
        border-top-color: #0A84FF !important;
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0A0A0A; }
    ::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ============ PARSE AI MARKERS ============
def parse_ai_response(text):
    if "[PRACTICE]" in text:
        match = re.search(r'\[PRACTICE\]\s*(.+)', text, re.DOTALL)
        if match:
            st.session_state.show_code_editor = True
            st.session_state.code_exercise = match.group(1).strip()
            st.session_state.code_ran = False
            st.session_state.code_output = ""
            st.session_state.code_error = ""
            st.session_state.has_plot = False
            st.session_state.current_plot = None

    if "[QUIZ]" in text:
        match = re.search(r'\[QUIZ\]\s*(.+)', text)
        if match:
            parts = text.split("[QUIZ]")[1].split("|")
            st.session_state.show_quiz = True
            st.session_state.quiz_question = parts[0].strip()
            st.session_state.quiz_options = [p.strip() for p in parts[1:] if p.strip()]

# ============ EXECUTE CODE ============
def execute_code(code):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    namespace = {"__name__": "__main__"}
    
    try:
        import numpy as np
        namespace['np'] = np
    except:
        pass
    try:
        import math
        namespace['math'] = math
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
        
    except Exception as e:
        output = stdout_capture.getvalue()
        tb = traceback.format_exc()
        return output, tb, False, None
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# ============ STREAMING AI RESPONSE ============
def get_ai_response_streaming(user_message, placeholder=None):
    if not API_KEY:
        return "⚠️ **Setup needed.** Add your API key in Streamlit Cloud → Settings → Secrets"
    
    try:
        client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
        
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        
        for msg in st.session_state.messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
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
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    clean = re.sub(r'\[PRACTICE\].*', '', full_response, flags=re.DOTALL)
                    clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
                    placeholder.markdown(clean + "▌")
            
            clean = re.sub(r'\[PRACTICE\].*', '', full_response, flags=re.DOTALL)
            clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
            placeholder.markdown(clean)
        else:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
        
        parse_ai_response(full_response)
        
        # Auto-save after every response
        save_history()
        
        return full_response
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            return "❌ **Invalid API key.**"
        elif "429" in error_msg:
            return "⏳ **Rate limit.** Wait a moment."
        else:
            return f"❌ **Error:** {error_msg[:100]}"

# ============ HEADER ============
st.markdown("""
<div class="app-header">
    <h1>Studio.</h1>
    <p>Topology Optimization & System Design</p>
</div>
""", unsafe_allow_html=True)

# ============ WELCOME BACK (if returning) ============
if len(st.session_state.messages) > 0:
    st.markdown(f"""
    <div class="welcome-back">
        <p>👋 Welcome back — your progress is saved. {len(st.session_state.messages)} messages in this session.</p>
    </div>
    """, unsafe_allow_html=True)

# ============ PROJECT SELECTION (Only if no history) ============
if len(st.session_state.messages) == 0:
    
    st.write("")
    
    # Topology Optimization
    st.markdown("""
    <div class="project-card" id="topopt-card">
        <h3>🏗️ Topology Optimization</h3>
        <p>Build a working structural optimization solver from scratch. Learn Python, NumPy, FEA, and the SIMP method — everything needed to create the tools engineers at Altair and Siemens use.</p>
        <span class="tag">Engineering · Python · FEA</span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Start Topology Optimization", use_container_width=True, type="primary"):
        st.session_state.current_track = "topology"
        st.session_state.messages.append({
            "role": "user", 
            "content": "I want to start the Topology Optimization track. I'm a complete beginner — teach me everything from scratch."
        })
        
        with st.chat_message("assistant"):
            placeholder = st.empty()
            response = get_ai_response_streaming(
                "I want to start the Topology Optimization track. I'm a complete beginner — teach me everything from scratch.",
                placeholder
            )
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_history()
        st.rerun()
    
    st.write("")
    
    # System Design
    st.markdown("""
    <div class="project-card" id="sysdesign-card">
        <h3>📐 System Design</h3>
        <p>Learn to design and build real software systems. From requirements to architecture to working code — the skills senior engineers use at Google, Netflix, and Uber.</p>
        <span class="tag">Architecture · Engineering · Code</span>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Start System Design", use_container_width=True, type="primary"):
        st.session_state.current_track = "system_design"
        st.session_state.messages.append({
            "role": "user",
            "content": "I want to start the System Design track. I'm a complete beginner — teach me everything from scratch."
        })
        
        with st.chat_message("assistant"):
            placeholder = st.empty()
            response = get_ai_response_streaming(
                "I want to start the System Design track. I'm a complete beginner — teach me everything from scratch.",
                placeholder
            )
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        save_history()
        st.rerun()
    
    st.write("")
    st.caption("Your progress is saved automatically — refresh anytime and continue where you left off.")
    st.write("")

# ============ CHAT HISTORY ============
for message in st.session_state.messages:
    clean = re.sub(r'\[PRACTICE\].*', '', message["content"], flags=re.DOTALL)
    clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
    with st.chat_message(message["role"]):
        st.write(clean)

# ============ PROGRESS ============
if len(st.session_state.messages) > 2:
    st.markdown(f"""
    <div class="progress-info">
        <span>Track: <span class="stat">{"Topology Optimization" if st.session_state.current_track == "topology" else "System Design"}</span></span>
        <span>💻 <span class="stat">{st.session_state.exercises_completed}</span> exercises completed</span>
    </div>
    """, unsafe_allow_html=True)

# ============ INLINE CODE EDITOR ============
if st.session_state.get("show_code_editor", False):
    
    st.markdown('<div class="section-label">📝 Practice</div>', unsafe_allow_html=True)
    
    st.info(f"**Your task:** {st.session_state.code_exercise}")
    
    code = st.text_area(
        "",
        value=st.session_state.code_content,
        height=180,
        key="code_editor",
        label_visibility="collapsed",
        placeholder="# Type your Python code here..."
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("▶  Run Code", use_container_width=True, type="primary"):
            st.session_state.code_content = code
            
            with st.spinner("Running..."):
                output, error, has_fig, fig = execute_code(code)
                st.session_state.code_output = output
                st.session_state.code_error = error
                st.session_state.code_ran = True
                st.session_state.has_plot = has_fig
                st.session_state.current_plot = fig
                save_history()
    
    with col2:
        if st.button("✓  Submit to Mentor", use_container_width=True):
            if not st.session_state.code_ran:
                st.warning("Run your code first, then submit.")
            else:
                submission = f"I completed the exercise.\n\nMy code:\n```python\n{code}\n```\n\n"
                
                if st.session_state.code_output:
                    submission += f"Output:\n```\n{st.session_state.code_output}\n```\n"
                
                if st.session_state.code_error and "Traceback" in st.session_state.code_error:
                    submission += f"I got an error — please help me fix it:\n```\n{st.session_state.code_error}\n```"
                else:
                    submission += "Please review my work."
                
                st.session_state.messages.append({"role": "user", "content": submission})
                st.session_state.exercises_completed += 1
                st.session_state.show_code_editor = False
                
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    response = get_ai_response_streaming(submission, placeholder)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_history()
                st.rerun()
    
    if st.session_state.code_ran:
        if st.session_state.code_output:
            st.markdown(f'<div class="output-box">✅ {st.session_state.code_output}</div>', unsafe_allow_html=True)
        if st.session_state.code_error and "Traceback" in st.session_state.code_error:
            error_lines = st.session_state.code_error.split('\n')
            clean_error = '\n'.join(error_lines[-5:])
            st.markdown(f'<div class="error-box">❌ {clean_error}</div>', unsafe_allow_html=True)

# ============ VISUALIZATION ============
if st.session_state.get("has_plot", False) and st.session_state.get("current_plot"):
    st.markdown('<div class="section-label">📊 Visualization</div>', unsafe_allow_html=True)
    try:
        st.pyplot(st.session_state.current_plot, use_container_width=True)
    except:
        st.caption("Plot could not be rendered.")
    st.write("")

# ============ QUIZ ============
if st.session_state.get("show_quiz", False):
    st.markdown(f'<div class="section-label">🤔 Quick Check</div>', unsafe_allow_html=True)
    st.write(f"**{st.session_state.quiz_question}**")
    st.write("")
    
    for i, option in enumerate(st.session_state.quiz_options):
        if st.button(option, key=f"quiz_{i}", use_container_width=True):
            st.session_state.show_quiz = False
            answer_msg = f"My answer: {option}"
            st.session_state.messages.append({"role": "user", "content": answer_msg})
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = get_ai_response_streaming(answer_msg, placeholder)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_history()
            st.rerun()

# ============ CHAT INPUT ============
if prompt := st.chat_input("Continue the conversation..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = get_ai_response_streaming(prompt, placeholder)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    save_history()
    st.rerun()

# ============ FOOTER / RESET ============
st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 2])
with col2:
    if st.button("🗑️ Reset", use_container_width=True):
        clear_history()
        st.rerun()

st.markdown("""
<div style="text-align: center; padding: 1rem 0; color: #3A3A3C; font-size: 0.6875rem;">
    Progress is saved automatically · Refresh anytime
</div>
""", unsafe_allow_html=True)
