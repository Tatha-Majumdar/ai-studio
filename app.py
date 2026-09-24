import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import json
import time

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"

# ============ SESSION STATE ============
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_start" not in st.session_state:
    st.session_state.pending_start = None
if "code_history" not in st.session_state:
    st.session_state.code_history = []
if "user_language" not in st.session_state:
    st.session_state.user_language = None
if "user_level" not in st.session_state:
    st.session_state.user_level = "absolute_beginner"
if "current_project" not in st.session_state:
    st.session_state.current_project = None
if "code_editor_content" not in st.session_state:
    st.session_state.code_editor_content = "# Write your code here\nprint('Hello, World!')"
if "code_output" not in st.session_state:
    st.session_state.code_output = ""
if "code_error" not in st.session_state:
    st.session_state.code_error = ""

# ============ API KEY ============
API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))

# ============ MENTOR BRAIN (Complete Curriculum System) ============
MENTOR_PROMPT = """
You are an expert engineering mentor inside an interactive learning platform. Your student has ZERO coding experience but wants to learn through building real projects. You teach EVERYTHING — from absolute basics to advanced concepts — adapted to their chosen language.

## YOUR FIRST TASK (Always do this at session start)
1. Greet the student warmly
2. Ask which programming language they want to learn (Python is recommended for beginners)
3. Ask what project interests them most
4. Assess their current knowledge (they said they know NOTHING, so start from zero)
5. Create a personalized learning path

## CURRICULUM DESIGN PRINCIPLES
- Project-driven: every concept is learned because the project needs it
- Just-in-time: teach concepts only when they're about to use them
- Scaffolded: start simple, add complexity gradually
- Hands-on: the student writes code after every concept
- Reviewed: you check their code like a senior engineer would
- Visualized: use the built-in sandbox to show plots and diagrams

## THE LEARNING CYCLE (repeat for each concept)
1. **Context**: "We need X for our project because..."
2. **Explanation**: Simple, clear explanation with analogy
3. **Example**: Show code in the chat
4. **Exercise**: "Now you try — write code that does..."
5. **Review**: Check their output, give feedback
6. **Apply**: Use the concept in the actual project

## CODE SANDBOX INSTRUCTIONS
When you want the student to write and run code:
- Provide the exercise clearly
- Tell them to use the "Code Sandbox" tab
- After they run it, review their output in the chat
- If there's an error, help them debug (don't just fix it for them)

## LANGUAGE-SPECIFIC TRACKS

### If they choose Python:
Week 1-2: print, variables, math, strings, input
Week 3-4: lists, loops, conditionals
Week 5-6: functions, dictionaries, file I/O
Week 7-8: error handling, modules, libraries
Week 9+: NumPy, matplotlib (for topology optimization)
Week 12+: Full project implementation

### If they choose JavaScript:
Adapt the same progression to JS syntax and concepts.

### If they choose another language:
Adapt accordingly, always project-driven.

## PROJECT TRACKS

### Track 1: Topology Optimization
For students interested in structural engineering:
- Build a SIMP-based topology optimizer
- Learn Python → NumPy → FEA basics → optimization
- Visualize structures using the sandbox
- Final deliverable: a working solver

### Track 2: System Design
For students interested in architecture:
- Build real systems (start with a URL shortener)
- Learn requirements → architecture → implementation
- Use diagrams in the visualization sandbox
- Final deliverable: a complete system they designed

### Track 3: Custom Project
For students with their own ideas:
- Understand their goal
- Break it into learnable components
- Guide them through building it step by step

## TEACHING STYLE
- Be encouraging but rigorous
- Use analogies from everyday life
- Show code examples that RUN (they can test in sandbox)
- When reviewing code: what's good, what to improve, what to fix
- If they're stuck: give a smaller version of the problem
- Celebrate their progress
- Keep momentum — always end with a clear next step

## SESSION CONTINUITY
- Remember what was taught in previous exchanges
- Reference earlier concepts when relevant
- Track progress and mention milestones
- Suggest review of earlier material if needed

## FORMAT YOUR RESPONSES
- Use clear headers
- Use code blocks for code examples
- Use bullet points for lists
- Keep explanations concise but complete
- End with a clear action for the student
"""

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio — Learn Everything",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============ APPLE HIG DARK MODE CSS ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    .stApp {
        background-color: #000000;
        color: #FFFFFF;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    
    #MainMenu, footer, header { visibility: hidden; }
    [data-testid="stSidebar"] { display: none !important; }
    
    .main-header {
        text-align: center;
        padding: 0.5rem 0 1.5rem 0;
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -0.04em;
        color: #FFFFFF;
        margin: 0;
    }
    
    .main-header p {
        font-size: 1rem;
        color: #8E8E93;
        font-weight: 400;
        margin-top: 0.3rem;
    }
    
    /* Project cards */
    .stButton > button {
        background: linear-gradient(180deg, #1C1C1E 0%, #2C2C2E 100%);
        color: #FFFFFF;
        border: 1px solid #3A3A3C;
        border-radius: 16px;
        padding: 1rem 1.25rem;
        font-weight: 500;
        font-size: 0.9rem;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        width: 100%;
        height: auto;
        transition: all 0.2s;
        text-align: left;
        line-height: 1.4;
        margin-bottom: 0.5rem;
    }
    
    .stButton > button:hover {
        background: linear-gradient(180deg, #2C2C2E 0%, #3A3A3C 100%);
        border-color: #0A84FF;
    }
    
    /* Chat */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.5rem 0;
    }
    
    [data-testid="stChatMessageContent"] {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #FFFFFF;
    }
    
    [data-testid="stChatMessage"] pre {
        background: #1C1C1E;
        border: 1px solid #3A3A3C;
        border-radius: 12px;
        padding: 1rem;
        font-size: 0.85rem;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
    }
    
    [data-testid="stChatMessage"] code {
        background: #2C2C2E;
        color: #0A84FF;
        padding: 0.125rem 0.375rem;
        border-radius: 6px;
        font-family: 'JetBrains Mono', 'SF Mono', monospace;
        font-size: 0.875em;
    }
    
    /* Chat input */
    [data-testid="stChatInput"] textarea {
        background: #1C1C1E !important;
        border: 1px solid #3A3A3C !important;
        border-radius: 22px !important;
        font-family: -apple-system, sans-serif !important;
        color: #FFFFFF !important;
        font-size: 1rem !important;
        padding: 0.875rem 1.25rem !important;
    }
    
    [data-testid="stChatInput"] textarea:focus {
        border-color: #0A84FF !important;
        background: #2C2C2E !important;
    }
    
    /* Code editor */
    .stTextArea textarea {
        background: #1C1C1E !important;
        border: 1px solid #3A3A3C !important;
        border-radius: 12px !important;
        font-family: 'JetBrains Mono', 'SF Mono', monospace !important;
        color: #FFFFFF !important;
        font-size: 0.875rem !important;
        line-height: 1.5 !important;
        padding: 1rem !important;
    }
    
    .stTextArea textarea:focus {
        border-color: #0A84FF !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: transparent;
        border-bottom: 1px solid #3A3A3C;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #8E8E93;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        font-size: 0.875rem;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #FFFFFF;
        background: #1C1C1E;
    }
    
    .stTabs [aria-selected="true"] {
        background: #1C1C1E !important;
        color: #0A84FF !important;
    }
    
    /* Output boxes */
    .output-box {
        background: #1C1C1E;
        border: 1px solid #3A3A3C;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #FFFFFF;
        white-space: pre-wrap;
    }
    
    .error-box {
        background: #2C1C1C;
        border: 1px solid #FF453A;
        border-radius: 12px;
        padding: 1rem;
        margin-top: 0.5rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #FF453A;
        white-space: pre-wrap;
    }
    
    /* Info callouts */
    .stInfo {
        background: #1C1C1E;
        border: 1px solid #0A84FF;
        border-radius: 12px;
    }
    
    /* Success */
    .stSuccess {
        background: #1C1C1E;
        border: 1px solid #30D158;
        border-radius: 12px;
    }
    
    /* Warning */
    .stWarning {
        background: #1C1C1E;
        border: 1px solid #FFD60A;
        border-radius: 12px;
    }
    
    /* Divider */
    hr {
        border: none;
        height: 1px;
        background: #3A3A3C;
        margin: 1.5rem auto;
    }
    
    /* Caption */
    .stCaption {
        color: #48484A;
    }
</style>
""", unsafe_allow_html=True)

# ============ FUNCTION: EXECUTE CODE ============
def execute_code(code):
    """Execute Python code and return output and errors."""
    
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = io.StringIO()
    redirected_error = io.StringIO()
    
    # Create a namespace for execution
    namespace = {"__name__": "__main__"}
    
    # Add common imports for convenience
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
    
    start_time = time.time()
    
    try:
        with contextlib.redirect_stdout(redirected_output):
            with contextlib.redirect_stderr(redirected_error):
                exec(code, namespace)
        
        output = redirected_output.getvalue()
        error = redirected_error.getvalue()
        execution_time = time.time() - start_time
        
        # Check if matplotlib was used
        has_figure = False
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            if plt.get_fignums():
                has_figure = True
        except:
            pass
        
        return output, error, execution_time, has_figure
        
    except Exception as e:
        output = redirected_output.getvalue()
        error = traceback.format_exc()
        execution_time = time.time() - start_time
        return output, error, execution_time, False
    
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# ============ FUNCTION: GET AI RESPONSE ============
def get_ai_response(user_message):
    """Send message to StepFun API and return response."""
    
    if not API_KEY:
        return "⚠️ **Setup needed.** Add your API key in Streamlit Cloud → Settings → Secrets"
    
    try:
        client = OpenAI(
            api_key=API_KEY,
            base_url=API_BASE_URL
        )
        
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        
        for msg in st.session_state.messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        api_messages.append({"role": "user", "content": user_message})
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=api_messages,
            max_tokens=4000,
            temperature=0.6
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            return "❌ Invalid API key."
        elif "404" in error_msg:
            return "❌ Model not found. Try 'step-1-8k'."
        else:
            return f"❌ Error: {error_msg[:150]}"

# ============ HEADER ============
st.markdown("""
<div class="main-header">
    <h1>Studio.</h1>
    <p>Learn to code. Build real projects. Everything included.</p>
</div>
""", unsafe_allow_html=True)

# ============ PROJECT SELECTION ============
if len(st.session_state.messages) == 0 and not st.session_state.pending_start:
    
    st.write("")
    st.markdown("##### Start your learning journey:")
    st.write("")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(
            "🏗️\n\n**Topology Optimization**\n\nLearn Python + engineering. Build a structural solver from zero.",
            use_container_width=True
        ):
            st.session_state.pending_start = "I want to learn everything from absolute zero and eventually build a topology optimization solver. I have no coding experience. Please create a learning plan for me and start with the very first lesson."
            st.rerun()
    
    with col2:
        if st.button(
            "📐\n\n**System Design**\n\nLearn coding + architecture. Build real systems from scratch.",
            use_container_width=True
        ):
            st.session_state.pending_start = "I want to learn coding from absolute zero and eventually build real systems. I have no coding experience. Please create a learning plan for me and start with the first lesson."
            st.rerun()
    
    st.write("")
    
    if st.button(
        "💻\n\n**Just Teach Me to Code**\n\nNo specific project yet — I just want to learn programming from zero.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I want to learn programming from absolute zero. I don't have a specific project in mind yet. Please ask me some questions to understand what I should learn and create a personalized curriculum."
        st.rerun()
    
    st.write("")
    st.caption("You'll get: interactive lessons, a code sandbox to practice, and a mentor that reviews your work.")

# ============ HANDLE PROJECT START ============
if st.session_state.pending_start:
    user_msg = st.session_state.pending_start
    st.session_state.pending_start = None
    
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.spinner("Creating your learning plan..."):
        response = get_ai_response(user_msg)
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    st.rerun()

# ============ MAIN INTERFACE (Tabs) ============
if len(st.session_state.messages) > 0:

    tab1, tab2, tab3 = st.tabs(["💬 Mentor", "💻 Code Sandbox", "📊 Visualize"])

    # ============ TAB 1: CHAT ============
    with tab1:
        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
        
        # Chat input
        if prompt := st.chat_input("Ask anything or submit your code output..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner(""):
                    response = get_ai_response(prompt)
                    st.write(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})

    # ============ TAB 2: CODE SANDBOX ============
    with tab2:
        st.markdown("##### 💻 Code Sandbox — Write and run code")
        st.write("")
        
        # Language info
        st.caption("Python execution environment. NumPy and math are pre-imported.")
        
        # Code editor
        code = st.text_area(
            "Code Editor",
            value=st.session_state.code_editor_content,
            height=300,
            key="code_input",
            label_visibility="collapsed"
        )
        
        # Buttons
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            if st.button("▶️ Run", use_container_width=True, type="primary"):
                st.session_state.code_editor_content = code
                
                with st.spinner("Running..."):
                    output, error, exec_time, has_plot = execute_code(code)
                    
                    st.session_state.code_output = output
                    st.session_state.code_error = error
                    
                    # Save to history
                    st.session_state.code_history.append({
                        "code": code,
                        "output": output,
                        "error": error,
                        "timestamp": time.strftime("%H:%M:%S")
                    })
        
        with col2:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.code_editor_content = "# Write your code here\nprint('Hello, World!')"
                st.session_state.code_output = ""
                st.session_state.code_error = ""
                st.rerun()
        
        with col3:
            if st.button("📤 Send to Mentor", use_container_width=True):
                # Create a message to send to the mentor
                code_result = f"I ran this code:\n```python\n{code}\n```\n\nOutput:\n```\n{st.session_state.code_output}\n```"
                if st.session_state.code_error:
                    code_result += f"\n\nError:\n```\n{st.session_state.code_error}\n```"
                
                st.session_state.messages.append({"role": "user", "content": code_result})
                
                with st.spinner("Mentor is reviewing your code..."):
                    response = get_ai_response(code_result)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                
                st.rerun()
        
        st.write("")
        
        # Display output
        if st.session_state.code_output:
            st.markdown("**Output:**")
            st.markdown(
                f'<div class="output-box">{st.session_state.code_output}</div>',
                unsafe_allow_html=True
            )
        
        # Display error
        if st.session_state.code_error:
            st.markdown("**Error:**")
            st.markdown(
                f'<div class="error-box">{st.session_state.code_error}</div>',
                unsafe_allow_html=True
            )
        
        # Execution history
        if st.session_state.code_history:
            st.write("")
            st.markdown("---")
            st.markdown("##### Recent Runs:")
            
            for i, entry in enumerate(reversed(st.session_state.code_history[-5:])):
                with st.expander(f"Run at {entry['timestamp']}"):
                    st.code(entry["code"], language="python")
                    if entry["output"]:
                        st.text_area("Output", entry["output"], height=100, disabled=True)

    # ============ TAB 3: VISUALIZATION ============
    with tab3:
        st.markdown("##### 📊 Visualization Sandbox — Plots and diagrams")
        st.write("")
        
        st.info("""
        This sandbox renders any matplotlib plots from your code runs.
        
        **How to use:**
        1. Go to the Code Sandbox tab
        2. Write code that creates a plot
        3. Run it
        4. Come back here to see the visualization
        """)
        
        # Check for any figures in the code history
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            
            # Try to get current figure from the last code run
            if len(st.session_state.code_history) > 0:
                last_code = st.session_state.code_history[-1]["code"]
                
                # Re-execute the code to get the plot
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                
                try:
                    namespace = {"__name__": "__main__"}
                    exec(last_code, namespace)
                    
                    # Check for figures
                    if plt.get_fignums():
                        st.pyplot(plt.gcf())
                    else:
                        st.caption("No plots detected. Write code that uses matplotlib to create visualizations.")
                        
                except:
                    st.caption("Run some code with matplotlib in the Code Sandbox first.")
                
                finally:
                    sys.stdout = old_stdout
            else:
                st.caption("Run some code in the Code Sandbox first.")
                
        except Exception as e:
            st.caption(f"Visualization not available: {str(e)}")

# ============ FOOTER ============
st.markdown("---")
st.caption("Studio — Everything you need to learn, build, and grow.")

# ============ CLEAR BUTTON (Subtle) ============
if len(st.session_state.messages) > 0:
    st.write("")
    if st.button("🗑️ Start Over (Clear All)"):
        st.session_state.messages = []
        st.session_state.code_history = []
        st.session_state.code_output = ""
        st.session_state.code_error = ""
        st.session_state.pending_start = None
        st.rerun()
