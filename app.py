import streamlit as st
from openai import OpenAI
import os

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"  # Hard-coded, no dropdown needed

# ============ MENTOR BRAIN ============
MENTOR_PROMPT = """
You are a senior engineering mentor. You guide learners through real, industry-grade projects.
You do NOT teach with lessons, quizzes, or abstract theory. You teach by BUILDING.

## Your Core Approach
- Every conversation is framed around building a real deliverable
- Introduce concepts only when the project needs them ("just-in-time")
- Act like a senior engineer working with a junior: explain WHY things are done
  a certain way in industry, not just how
- Give the learner actual tasks to implement, then review their work
- Use industry-standard terminology, tools, and conventions
- When reviewing work: what's solid, what needs fixing, what the industry
  standard approach would be, then let them fix it
- Keep momentum — always end with a clear next step

## Project Structure
1. **Project Brief** — what we're building, why it matters in industry
2. **Scope** — what's in, what's out, what "done" looks like
3. **Architecture** — how components fit together
4. **Build** — implement step by step
5. **Review** — test, document, discuss trade-offs
6. **Ship** — how this gets deployed in a real environment

## Active Project Tracks

### Track 1: Topology Optimization Solver (Python)
Guide the learner to build a working structural optimization solver from scratch.
- Start with: 2D cantilever beam, SIMP method, compliance minimization
- Python is learned as needed: NumPy, matplotlib, SciPy
- Progress: design domains, sensitivity analysis, density filters
- Industry context: how Altair OptiStruct and Abaqus Tosca work

### Track 2: System Design Studio
Guide through designing and implementing real systems.
- Start with: a complete but simple system (e.g., URL shortener)
- Learn: requirements → architecture → build → bottlenecks → improve
- Industry context: how Netflix, Uber, Google solve these problems

### Track 3: Custom Project
If the learner has their own idea, mentor them through it.

## Communication Rules
- Direct and professional, like a senior colleague
- Code follows industry conventions
- When reviewing code: what works, what breaks, what to fix
- If stuck, reduce to a smaller problem and let them solve it
- Track project progress across the conversation

## Session Start
When the learner first arrives, ask which project they want to work on.
"""

# ============ SESSION STATE ============
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_start" not in st.session_state:
    st.session_state.pending_start = None

# ============ READ API KEY (INVISIBLE) ============
# Reads from Streamlit Cloud secrets — never shown to anyone
API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))

# ============ CSS (Apple-Style, Minimal) ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
        background: #ffffff;
    }
    
    /* Hide ALL Streamlit chrome */
    #MainMenu, footer, header {
        visibility: hidden;
    }
    
    /* Hide sidebar completely */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    .block-container {
        padding-top: 2rem;
        padding-bottom: 6rem;
        max-width: 680px;
    }
    
    .main-header {
        text-align: center;
        padding: 0.5rem 0;
        margin-bottom: 1rem;
    }
    
    .main-header h1 {
        font-size: 3rem;
        font-weight: 700;
        letter-spacing: -0.045em;
        color: #1d1d1f;
        margin: 0;
    }
    
    .main-header p {
        font-size: 1.1rem;
        color: #86868b;
        font-weight: 400;
        margin-top: 0.4rem;
    }
    
    /* Project buttons — Apple card style */
    .stButton > button {
        background: #f5f5f7;
        color: #1d1d1f;
        border: 1px solid #e8e8ed;
        border-radius: 18px;
        padding: 1.25rem 1.5rem;
        font-weight: 500;
        font-size: 0.95rem;
        font-family: 'Inter', sans-serif;
        width: 100%;
        height: auto;
        transition: all 0.2s;
        text-align: left;
        line-height: 1.5;
        margin-bottom: 0.5rem;
    }
    
    .stButton > button:hover {
        background: #ffffff;
        border-color: #0071e3;
        box-shadow: 0 2px 16px rgba(0,0,0,0.08);
    }
    
    /* Chat messages */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.5rem 0;
    }
    
    [data-testid="stChatMessageContent"] {
        font-size: 0.95rem;
        line-height: 1.6;
        color: #1d1d1f;
    }
    
    /* Chat input */
    [data-testid="stChatInput"] {
        border-radius: 22px;
    }
    
    [data-testid="stChatInput"] textarea {
        border-radius: 22px !important;
        font-family: 'Inter', sans-serif !important;
        border: 1px solid #d2d2d7 !important;
    }
    
    [data-testid="stChatInput"] textarea:focus {
        border-color: #0071e3 !important;
    }
    
    /* Code blocks in chat */
    [data-testid="stChatMessage"] pre {
        background: #1d1d1f;
        border-radius: 14px;
        padding: 1rem;
        font-size: 0.85rem;
    }
    
    [data-testid="stChatMessage"] code {
        font-family: 'SF Mono', 'Menlo', monospace;
    }
</style>
""", unsafe_allow_html=True)

# ============ FUNCTION: GET AI RESPONSE ============
def get_ai_response(user_message):
    """Send message to StepFun API and return response."""
    
    if not API_KEY:
        return "⚠️ **Setup needed.**\n\nGo to your Streamlit Cloud app settings → Secrets → add:\n```\nSTEPFUN_API_KEY = \"your_key_here\"\n```"
    
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
            return "❌ **API key invalid.** Check your key in Streamlit Cloud secrets."
        elif "404" in error_msg:
            return f"❌ **Model not found.** The model `{MODEL_NAME}` might not be available on your key."
        elif "429" in error_msg:
            return "⏳ **Rate limit.** Wait a moment and try again."
        else:
            return f"❌ **Error:** {error_msg[:150]}"

# ============ MAIN PAGE ============

# Header
st.markdown("""
<div class="main-header">
    <h1>Studio.</h1>
    <p>Build real projects. Learn by doing.</p>
</div>
""", unsafe_allow_html=True)

# ============ PROJECT SELECTION ============
if len(st.session_state.messages) == 0 and not st.session_state.pending_start:
    
    st.write("")
    
    # Topology Optimization
    if st.button(
        "🏗️  Topology Optimization\n\nBuild a working SIMP solver. Learn Python, FEA, and structural design.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I want to start the topology optimization project. Give me the project brief and scope."
        st.rerun()
    
    # System Design
    if st.button(
        "📐  System Design\n\nDesign and build real systems from requirements to working code.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I want to start the system design project. Give me the project brief and scope."
        st.rerun()
    
    # Custom
    if st.button(
        "💡  Your Own Project\n\nHave an idea? Start here and the mentor will guide you.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I have my own project idea I want to work on. What do you need to know to get started?"
        st.rerun()
    
    st.write("")
    st.caption("— or type below —")

# ============ HANDLE PROJECT START ============
if st.session_state.pending_start:
    user_msg = st.session_state.pending_start
    st.session_state.pending_start = None
    
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    with st.spinner("Starting your project..."):
        response = get_ai_response(user_msg)
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    st.rerun()

# ============ DISPLAY CHAT ============
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ============ CHAT INPUT ============
if prompt := st.chat_input("Type here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = get_ai_response(prompt)
            st.write(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})

# ============ FOOTER ============
st.write("")
st.caption("Studio — Project-based engineering mentorship")
