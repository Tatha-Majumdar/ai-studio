import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import time
import re
import base64

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"

# ============ SESSION STATE ============
def init_state():
    defaults = {
        "messages": [],
        "pending_start": None,
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
        "concepts_learned": [],
        "exercises_completed": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_state()

# ============ API KEY ============
API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))

# ============ MENTOR SYSTEM PROMPT ============
MENTOR_PROMPT = """
You are an expert mentor in an interactive learning platform. Your student has ZERO coding experience. You teach everything from absolute basics to advanced engineering, project-driven.

## CONTROLLING THE PLATFORM

You control what the student sees. Use these markers:

**[PRACTICE]** — Shows a code editor. Format:
End your message with [PRACTICE] followed by a clear, single-task exercise.
Example: [PRACTICE] Create a variable called name, assign your name to it, then print it.

**[QUIZ]** — Shows interactive quiz buttons. Format:
[QUIZ] What does print() do? | Displays text | Deletes files | Creates variables | Nothing

**[VISUAL]** — Tells the student to run code that creates a plot. Use when teaching concepts that benefit from visualization.

Use markers ONLY when practice or checking is needed. Otherwise just explain.

## TEACHING FLOW (per concept)

1. **Introduce**: Why this concept matters for the project
2. **Explain**: Simple, clear explanation with analogy  
3. **Show**: Code example in the chat
4. **Practice**: [PRACTICE] exercise for the student
5. **Review**: When they submit code, review it: what's good, what to fix, then move forward
6. **Quiz** (occasionally): [QUIZ] to check understanding

## CURRICULUM — START FROM ZERO

The student knows NOTHING. Begin with:
- What is a program? What is Python?
- print() — the simplest possible program
- Variables — storing information
- Then progressively: math, strings, lists, loops, functions, etc.

Every concept must connect to the project they're building toward.

## WHEN REVIEWING CODE

- Start with what they did RIGHT (be specific)
- Then identify issues (gently, clearly)
- If there's an error, explain what the error MEANS
- Give them a chance to fix it themselves before showing the answer
- If they're really stuck, provide the corrected code with explanation

## SESSION START

Greet warmly. Ask:
1. What are you excited to build?
2. Confirm Python (best for beginners)
Then immediately start with lesson 1: what is a program, and print().

## STYLE
- Encouraging but rigorous
- One concept at a time — don't overwhelm
- Use everyday analogies
- Code examples that actually work
- Short messages (100-200 words) — don't lecture
- Always end with a clear next action

## IMPORTANT
- Never skip basics assuming they know something
- If they mention knowing something, verify with a quick question
- Track what's been learned and reference it
- If they struggle, simplify — don't skip
"""

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio — Learn Everything",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ============ PREMIUM DARK MODE CSS ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ============ BASE ============ */
    .stApp {
        background: #0A0A0A;
        color: #F5F5F5;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
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

    /* ============ HEADER ============ */
    .app-header {
        text-align: center;
        padding: 2.5rem 0 1.5rem 0;
        border-bottom: 1px solid #1A1A1A;
        margin-bottom: 0;
    }

    .app-header h1 {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.05em;
        color: #F5F5F5;
        margin: 0;
        line-height: 1;
    }

    .app-header .tagline {
        font-size: 0.875rem;
        color: #6E6E73;
        font-weight: 400;
        margin-top: 0.5rem;
        letter-spacing: -0.01em;
    }

    /* ============ CHAT ============ */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.375rem 0;
        margin: 0;
    }

    [data-testid="stChatMessageContent"] {
        font-size: 0.9375rem;
        line-height: 1.7;
        color: #F5F5F5;
        font-weight: 400;
        letter-spacing: -0.01em;
    }

    [data-testid="stChatMessage"] p {
        margin-bottom: 0.75rem;
    }

    [data-testid="stChatMessage"] strong {
        font-weight: 600;
        color: #FFFFFF;
    }

    /* Code blocks in chat */
    [data-testid="stChatMessage"] pre {
        background: #141414;
        border: 1px solid #262626;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        font-size: 0.8125rem;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        line-height: 1.6;
        color: #E0E0E0;
        overflow-x: auto;
    }

    [data-testid="stChatMessage"] code {
        background: #1E1E1E;
        color: #7DD3FC;
        padding: 2px 7px;
        border-radius: 5px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85em;
        border: 1px solid #2A2A2A;
    }

    [data-testid="stChatMessage"] pre code {
        background: transparent;
        border: none;
        padding: 0;
        color: inherit;
        font-size: inherit;
    }

    /* Headers in chat */
    [data-testid="stChatMessage"] h1,
    [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3 {
        color: #F5F5F5;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin-top: 1.25rem;
        margin-bottom: 0.5rem;
    }

    [data-testid="stChatMessage"] h1 { font-size: 1.375rem; }
    [data-testid="stChatMessage"] h2 { font-size: 1.1875rem; }
    [data-testid="stChatMessage"] h3 { font-size: 1rem; }

    /* Lists */
    [data-testid="stChatMessage"] ul,
    [data-testid="stChatMessage"] ol {
        padding-left: 1.25rem;
        margin: 0.5rem 0;
    }

    [data-testid="stChatMessage"] li {
        margin-bottom: 0.375rem;
        color: #D0D0D0;
    }

    /* Blockquotes */
    [data-testid="stChatMessage"] blockquote {
        border-left: 3px solid #0A84FF;
        padding-left: 1rem;
        margin: 0.75rem 0;
        color: #A0A0A5;
        font-style: italic;
    }

    /* ============ CHAT INPUT ============ */
    [data-testid="stChatInput"] {
        position: sticky;
        bottom: 0;
        padding: 1rem 0;
        background: linear-gradient(to bottom, transparent, #0A0A0A 80%);
    }

    [data-testid="stChatInput"] textarea {
        background: #141414 !important;
        border: 1px solid #2A2A2A !important;
        border-radius: 18px !important;
        color: #F5F5F5 !important;
        font-size: 0.9375rem !important;
        font-family: 'Inter', sans-serif !important;
        padding: 0.75rem 1.25rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
        transition: all 0.15s ease !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: #0A84FF !important;
        background: #1A1A1A !important;
        box-shadow: 0 0 0 3px rgba(10,132,255,0.15), 0 2px 8px rgba(0,0,0,0.3) !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #48484A !important;
    }

    /* ============ CODE EDITOR ============ */
    .code-section {
        background: #0D0D0D;
        border: 1px solid #1E1E1E;
        border-radius: 16px;
        margin: 1.5rem 0;
        overflow: hidden;
    }

    .code-section-header {
        background: #141414;
        border-bottom: 1px solid #1E1E1E;
        padding: 0.75rem 1.25rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .code-section-header .label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #0A84FF;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .code-section-header .lang {
        font-size: 0.75rem;
        color: #48484A;
        font-family: 'JetBrains Mono', monospace;
    }

    .stTextArea textarea {
        background: #0A0A0A !important;
        border: none !important;
        border-radius: 0 !important;
        font-family: 'JetBrains Mono', monospace !important;
        color: #E0E0E0 !important;
        font-size: 0.875rem !important;
        line-height: 1.7 !important;
        padding: 1rem 1.25rem !important;
        min-height: 180px !important;
    }

    .stTextArea textarea:focus {
        background: #0A0A0A !important;
    }

    .stTextArea textarea::placeholder {
        color: #333333 !important;
    }

    /* ============ OUTPUT ============ */
    .output-section {
        background: #0D0D0D;
        border-top: 1px solid #1E1E1E;
        padding: 1rem 1.25rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        line-height: 1.6;
    }

    .output-label {
        font-size: 0.6875rem;
        font-weight: 600;
        color: #30D158;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }

    .output-label.error {
        color: #FF453A;
    }

    .output-content {
        color: #30D158;
        white-space: pre-wrap;
    }

    .output-content.error {
        color: #FF453A;
    }

    /* ============ BUTTONS ============ */
    .stButton > button {
        background: #0A84FF;
        color: #FFFFFF;
        border: none;
        border-radius: 12px;
        padding: 0.625rem 1.5rem;
        font-weight: 600;
        font-size: 0.875rem;
        font-family: 'Inter', sans-serif;
        letter-spacing: -0.01em;
        transition: all 0.15s ease;
        box-shadow: 0 2px 8px rgba(10,132,255,0.3);
    }

    .stButton > button:hover {
        background: #409CFF;
        box-shadow: 0 4px 16px rgba(10,132,255,0.4);
        transform: translateY(-1px);
    }

    .stButton > button:active {
        transform: translateY(0);
    }

    .stButton > button[kind="secondary"] {
        background: #1E1E1E;
        color: #A0A0A5;
        border: 1px solid #2A2A2A;
        box-shadow: none;
    }

    .stButton > button[kind="secondary"]:hover {
        background: #2A2A2A;
        color: #F5F5F5;
        border-color: #3A3A3A;
    }

    /* ============ QUIZ ============ */
    .quiz-section {
        background: #0D0D0D;
        border: 1px solid #1E1E1E;
        border-radius: 16px;
        margin: 1.5rem 0;
        padding: 1.25rem;
    }

    .quiz-question {
        font-size: 1rem;
        font-weight: 600;
        color: #F5F5F5;
        margin-bottom: 1rem;
    }

    /* ============ MISC ============ */
    [data-testid="stSpinner"] > div {
        border-top-color: #0A84FF !important;
    }

    hr {
        border: none;
        height: 1px;
        background: #1A1A1A;
        margin: 1.5rem 0;
    }

    .stCaption {
        color: #3A3A3C;
        font-size: 0.75rem;
    }

    .stInfo {
        background: #0D0D0D;
        border: 1px solid #0A84FF;
        border-radius: 12px;
        color: #A0C4FF;
    }

    .stWarning {
        background: #1A1A0D;
        border: 1px solid #FFD60A;
        border-radius: 12px;
        color: #FFD60A;
    }

    /* Progress indicator */
    .progress-bar {
        background: #1A1A1A;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.75rem;
        color: #6E6E73;
        margin-bottom: 1rem;
    }

    .progress-stat {
        font-weight: 600;
        color: #0A84FF;
    }

    /* Animated typing indicator */
    .typing-indicator {
        display: flex;
        gap: 4px;
        padding: 0.5rem 0;
    }

    .typing-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #0A84FF;
        opacity: 0.3;
        animation: typing 1.4s infinite;
    }

    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }

    @keyframes typing {
        0%, 60%, 100% { opacity: 0.3; transform: scale(1); }
        30% { opacity: 1; transform: scale(1.1); }
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
    }

    ::-webkit-scrollbar-track {
        background: #0A0A0A;
    }

    ::-webkit-scrollbar-thumb {
        background: #2A2A2A;
        border-radius: 3px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #3A3A3A;
    }

    /* Expander */
    .streamlit-expanderHeader {
        background: #141414;
        color: #A0A0A5;
        border: 1px solid #2A2A2A;
        border-radius: 10px;
        font-size: 0.875rem;
    }
</style>
""", unsafe_allow_html=True)

# ============ PARSE AI MARKERS ============
def parse_ai_response(text):
    """Detect markers in AI response and set up UI elements."""
    
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
    """Execute Python code, capture output, errors, and matplotlib figures."""
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    namespace = {"__name__": "__main__"}
    
    # Pre-import useful libraries
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
    
    # Set up matplotlib for headless operation
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        namespace['plt'] = plt
        namespace['matplotlib'] = matplotlib
    except:
        pass
    
    try:
        with contextlib.redirect_stdout(stdout_capture):
            with contextlib.redirect_stderr(stderr_capture):
                exec(code, namespace)
        
        output = stdout_capture.getvalue()
        error = stderr_capture.getvalue()
        
        # Check for matplotlib figures
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
def get_ai_response_streaming(user_message, display_placeholder=None):
    """Get streaming response from StepFun API."""
    
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
        
        # Streaming
        stream = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages,
            stream=True,
            max_tokens=4000,
            temperature=0.6
        )
        
        full_response = ""
        
        if display_placeholder:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    # Clean markers for display
                    clean = re.sub(r'\[PRACTICE\].*', '', full_response, flags=re.DOTALL)
                    clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
                    display_placeholder.markdown(clean + "▌")
            
            # Final clean version
            clean = re.sub(r'\[PRACTICE\].*', '', full_response, flags=re.DOTALL)
            clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
            display_placeholder.markdown(clean)
        else:
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
        
        # Parse for markers
        parse_ai_response(full_response)
        
        # Track concepts
        if "variable" in full_response.lower():
            if "variables" not in st.session_state.concepts_learned:
                st.session_state.concepts_learned.append("variables")
        
        return full_response
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            return "❌ **Invalid API key.** Check your Streamlit Cloud secrets."
        elif "404" in error_msg:
            return "❌ **Model not found.** The model might not be available on your key."
        elif "429" in error_msg:
            return "⏳ **Rate limit.** Please wait a moment and try again."
        else:
            return f"❌ **Error:** {error_msg[:100]}"

# ============ DISPLAY MESSAGE (Clean) ============
def display_message(content, role):
    """Display a message, removing internal markers."""
    clean = re.sub(r'\[PRACTICE\].*', '', content, flags=re.DOTALL)
    clean = re.sub(r'\[QUIZ\].*', '', clean, flags=re.DOTALL)
    with st.chat_message(role):
        st.write(clean)

# ============ HEADER ============
st.markdown("""
<div class="app-header">
    <h1>Studio.</h1>
    <p class="tagline">Learn to code. Build real projects.</p>
</div>
""", unsafe_allow_html=True)

# ============ START SCREEN ============
if len(st.session_state.messages) == 0 and not st.session_state.pending_start:
    
    st.write("")
    st.write("")
    
    if st.button(
        "🚀  Start Learning",
        use_container_width=True,
        type="primary"
    ):
        st.session_state.pending_start = "I'm ready to start learning from absolute zero. I don't know anything about coding. Please assess what I want to build and start teaching me from the very first concept."
        st.rerun()
    
    st.write("")
    st.write("")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("📚 Concepts")
        st.caption("0 learned")
    with col2:
        st.caption("💻 Exercises")  
        st.caption("0 completed")
    with col3:
        st.caption("📊 Progress")
        st.caption("Just starting")

# ============ HANDLE START ============
if st.session_state.pending_start:
    user_msg = st.session_state.pending_start
    st.session_state.pending_start = None
    
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = get_ai_response_streaming(user_msg, placeholder)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# ============ PROGRESS BAR ============
if len(st.session_state.messages) > 2:
    concepts = len(st.session_state.concepts_learned)
    exercises = st.session_state.exercises_completed
    
    st.markdown(f"""
    <div class="progress-bar">
        <span>📚 {concepts} concept{'s' if concepts != 1 else ''} learned</span>
        <span>💻 {exercises} exercise{'s' if exercises != 1 else ''} completed</span>
    </div>
    """, unsafe_allow_html=True)

# ============ CHAT HISTORY ============
for message in st.session_state.messages:
    display_message(message["content"], message["role"])

# ============ INLINE CODE EDITOR ============
if st.session_state.get("show_code_editor", False):
    
    st.markdown("""
    <div class="code-section">
        <div class="code-section-header">
            <span class="label">📝 Practice</span>
            <span class="lang">python</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Exercise description
    st.info(f"**Your task:** {st.session_state.code_exercise}")
    
    # Code editor
    code = st.text_area(
        "",
        value=st.session_state.code_content,
        height=180,
        key=f"code_editor_{st.session_state.exercises_completed}",
        label_visibility="collapsed",
        placeholder="# Type your Python code here..."
    )
    
    # Action buttons
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("▶  Run", use_container_width=True, type="primary"):
            st.session_state.code_content = code
            
            with st.spinner("Running..."):
                output, error, has_fig, fig = execute_code(code)
                st.session_state.code_output = output
                st.session_state.code_error = error
                st.session_state.code_ran = True
                st.session_state.has_plot = has_fig
                st.session_state.current_plot = fig
    
    with col2:
        if st.button("✓  Submit to Mentor", use_container_width=True):
            if not st.session_state.code_ran:
                st.warning("Run your code first, then submit.")
            else:
                # Build submission
                submission = f"I completed the exercise.\n\nMy code:\n```python\n{code}\n```\n\n"
                
                if st.session_state.code_output:
                    submission += f"Output:\n```\n{st.session_state.code_output}\n```\n"
                
                if st.session_state.code_error and st.session_state.code_error != "":
                    submission += f"I got an error:\n```\n{st.session_state.code_error}\n```\nPlease help me fix it."
                else:
                    submission += "Please review my work."
                
                # Add to chat
                st.session_state.messages.append({"role": "user", "content": submission})
                
                # Update stats
                st.session_state.exercises_completed += 1
                
                # Hide editor
                st.session_state.show_code_editor = False
                
                # Get AI review
                with st.chat_message("assistant"):
                    placeholder = st.empty()
                    response = get_ai_response_streaming(submission, placeholder)
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()
    
    # Output display
    if st.session_state.code_ran:
        if st.session_state.code_output:
            st.markdown(f"""
            <div class="code-section">
                <div class="output-section">
                    <div class="output-label">Output</div>
                    <div class="output-content">{st.session_state.code_output}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if st.session_state.code_error and "Traceback" in st.session_state.code_error:
            # Clean up traceback for display
            error_lines = st.session_state.code_error.split('\n')
            clean_error = '\n'.join(error_lines[-5:]) if len(error_lines) > 5 else st.session_state.code_error
            
            st.markdown(f"""
            <div class="code-section">
                <div class="output-section">
                    <div class="output-label error">Error</div>
                    <div class="output-content error">{clean_error}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ============ INLINE VISUALIZATION ============
if st.session_state.get("has_plot", False) and st.session_state.get("current_plot"):
    
    st.markdown("""
    <div class="code-section">
        <div class="code-section-header">
            <span class="label">📊 Visualization</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    try:
        st.pyplot(st.session_state.current_plot, use_container_width=True)
    except:
        st.caption("Plot could not be rendered.")
    
    st.write("")

# ============ INLINE QUIZ ============
if st.session_state.get("show_quiz", False):
    
    st.markdown(f"""
    <div class="quiz-section">
        <div class="quiz-question">🤔 {st.session_state.quiz_question}</div>
    </div>
    """, unsafe_allow_html=True)
    
    for i, option in enumerate(st.session_state.quiz_options):
        if st.button(option, key=f"quiz_option_{i}", use_container_width=True):
            st.session_state.show_quiz = False
            
            answer_msg = f"My answer: {option}"
            st.session_state.messages.append({"role": "user", "content": answer_msg})
            
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = get_ai_response_streaming(answer_msg, placeholder)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
    
    st.write("")

# ============ CHAT INPUT ============
if prompt := st.chat_input("Ask anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = get_ai_response_streaming(prompt, placeholder)
    
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# ============ RESET (Subtle) ============
if len(st.session_state.messages) > 5:
    st.write("")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Start Over", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            init_state()
            st.rerun()

# ============ FOOTER ============
st.markdown("""
<div style="text-align: center; padding: 2rem 0 1rem 0; border-top: 1px solid #1A1A1A; margin-top: 2rem;">
    <span style="color: #3A3A3C; font-size: 0.6875rem; letter-spacing: 0.02em;">STUDIO</span>
</div>
""", unsafe_allow_html=True)
