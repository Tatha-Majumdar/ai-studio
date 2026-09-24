import streamlit as st
from openai import OpenAI
import os

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"

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

# ============ API KEY (Hidden) ============
API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))

# ============ APPLE HIG DARK MODE CSS ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* Apple Dark Mode Base */
    .stApp {
        background-color: #000000; /* System background */
        color: #FFFFFF; /* Primary text */
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    /* Hide all Streamlit chrome */
    #MainMenu, footer, header {
        visibility: hidden;
    }
    
    /* Hide sidebar completely */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    
    /* Container */
    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 7rem;
        max-width: 680px;
    }
    
    /* ============ TYPOGRAPHY ============ */
    .main-header {
        text-align: center;
        padding: 0 0 2rem 0;
    }
    
    .main-header h1 {
        font-size: 3rem;
        font-weight: 700;
        letter-spacing: -0.04em; /* Apple's tight tracking for large text */
        color: #FFFFFF;
        margin: 0;
        line-height: 1.05;
    }
    
    .main-header .subtitle {
        font-size: 1.125rem;
        font-weight: 400;
        color: #8E8E93; /* Secondary label color */
        letter-spacing: -0.01em;
        margin-top: 0.5rem;
        line-height: 1.4;
    }
    
    /* ============ PROJECT CARDS (Elevated Surfaces) ============ */
    .stButton > button {
        /* Apple elevated surface */
        background: linear-gradient(180deg, #1C1C1E 0%, #2C2C2E 100%);
        color: #FFFFFF;
        border: 1px solid #3A3A3C; /* Separator color */
        border-radius: 16px; /* Apple's standard corner radius */
        padding: 1.25rem 1.5rem;
        font-weight: 500;
        font-size: 1rem;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        width: 100%;
        height: auto;
        transition: all 0.2s cubic-bezier(0.25, 0.1, 0.25, 1);
        text-align: left;
        line-height: 1.4;
        margin-bottom: 0.75rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(180deg, #2C2C2E 0%, #3A3A3C 100%);
        border-color: #48484A;
        box-shadow: 0 2px 12px rgba(0,0,0,0.5);
    }
    
    .stButton > button:focus {
        outline: none;
        border-color: #0A84FF; /* Apple blue */
        box-shadow: 0 0 0 3px rgba(10,132,255,0.3);
    }
    
    /* ============ CHAT MESSAGES ============ */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.75rem 0;
        border-radius: 0;
    }
    
    [data-testid="stChatMessageContent"] {
        font-size: 1rem;
        line-height: 1.6;
        color: #FFFFFF;
        font-weight: 400;
    }
    
    /* Code blocks */
    [data-testid="stChatMessage"] pre {
        background: #1C1C1E; /* Elevated surface */
        border: 1px solid #3A3A3C;
        border-radius: 12px;
        padding: 1rem;
        font-size: 0.875rem;
        color: #FFFFFF;
        font-family: 'SF Mono', 'Menlo', monospace;
    }
    
    [data-testid="stChatMessage"] code {
        font-family: 'SF Mono', 'Menlo', monospace;
        background: #2C2C2E;
        color: #0A84FF;
        padding: 0.125rem 0.375rem;
        border-radius: 6px;
        font-size: 0.875em;
    }
    
    /* Headers inside chat */
    [data-testid="stChatMessage"] h1,
    [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3 {
        color: #FFFFFF;
        font-weight: 600;
        letter-spacing: -0.02em;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    [data-testid="stChatMessage"] h1 { font-size: 1.5rem; }
    [data-testid="stChatMessage"] h2 { font-size: 1.25rem; }
    [data-testid="stChatMessage"] h3 { font-size: 1.125rem; }
    
    /* Lists */
    [data-testid="stChatMessage"] ul,
    [data-testid="stChatMessage"] ol {
        padding-left: 1.5rem;
        margin: 0.75rem 0;
    }
    
    /* ============ CHAT INPUT ============ */
    [data-testid="stChatInput"] {
        border-radius: 22px;
    }
    
    [data-testid="stChatInput"] textarea {
        background: #1C1C1E !important;
        border: 1px solid #3A3A3C !important;
        border-radius: 22px !important;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif !important;
        color: #FFFFFF !important;
        font-size: 1rem !important;
        padding: 0.875rem 1.25rem !important;
        box-shadow: 0 1px 6px rgba(0,0,0,0.3) !important;
        transition: all 0.2s !important;
    }
    
    [data-testid="stChatInput"] textarea:focus {
        border-color: #0A84FF !important;
        box-shadow: 0 0 0 3px rgba(10,132,255,0.2), 0 1px 6px rgba(0,0,0,0.3) !important;
        background: #2C2C2E !important;
    }
    
    [data-testid="stChatInput"] textarea::placeholder {
        color: #8E8E93 !important;
    }
    
    /* ============ OTHER ELEMENTS ============ */
    .stSpinner > div {
        border-top-color: #0A84FF !important;
    }
    
    /* Divider */
    hr {
        border: none;
        height: 1px;
        background: #3A3A3C;
        margin: 2rem auto;
        max-width: 100%;
    }
    
    /* Caption text */
    .stCaption, .stMarkdown p {
        color: #8E8E93;
    }
    
    /* Error messages */
    [data-testid="stError"] {
        background: #1C1C1E;
        border: 1px solid #FF453A; /* Apple red */
        border-radius: 12px;
        color: #FF453A;
    }
    
    /* Success messages */
    [data-testid="stSuccess"] {
        background: #1C1C1E;
        border: 1px solid #30D158; /* Apple green */
        border-radius: 12px;
        color: #30D158;
    }
    
    /* Warning messages */
    [data-testid="stWarning"] {
        background: #1C1C1E;
        border: 1px solid #FFD60A; /* Apple yellow */
        border-radius: 12px;
        color: #FFD60A;
    }
    
    /* Footer */
    .app-footer {
        text-align: center;
        color: #48484A; /* Tertiary label */
        font-size: 0.8125rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #3A3A3C;
    }
</style>
""", unsafe_allow_html=True)

# ============ FUNCTION: GET AI RESPONSE ============
def get_ai_response(user_message):
    """Send message to StepFun API and return response."""
    
    if not API_KEY:
        return """
        ⚠️ **Setup Required**
        
        Your API key isn't configured yet.
        
        **How to fix:**
        1. Go to your Streamlit Cloud app
        2. Click Settings → Secrets
        3. Add: `STEPFUN_API_KEY = "your_key_here"`
        """
    
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
            return "❌ **Invalid API key.** Check your key in Streamlit Cloud secrets."
        elif "404" in error_msg:
            return f"❌ **Model not found.** `{MODEL_NAME}` might not be available."
        elif "429" in error_msg:
            return "⏳ **Rate limit.** Wait a moment and try again."
        else:
            return f"❌ **Error:** {error_msg[:150]}"

# ============ MAIN PAGE ============

# Header
st.markdown("""
<div class="main-header">
    <h1>Studio.</h1>
    <p class="subtitle">Build real projects. Learn by doing.</p>
</div>
""", unsafe_allow_html=True)

# ============ PROJECT SELECTION ============
if len(st.session_state.messages) == 0 and not st.session_state.pending_start:
    
    st.markdown("##### Choose a project:")
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
        "💡  Custom Project\n\nHave your own idea? The mentor will guide you through it.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I have my own project idea. What do you need to know to get started?"
        st.rerun()
    
    st.markdown("---")
    st.caption("Or type your message below")

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
if prompt := st.chat_input("Message"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner(""):
            response = get_ai_response(prompt)
            st.write(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})

# ============ FOOTER ============
st.markdown("""
<div class="app-footer">
    Studio — Project-based engineering mentorship
</div>
""", unsafe_allow_html=True)
