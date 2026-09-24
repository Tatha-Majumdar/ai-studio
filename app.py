import streamlit as st
from openai import OpenAI
import os

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"

# ============ PAGE SETUP ============
st.set_page_config(
    page_title="Studio — Project-Based Learning",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded"  # Changed: sidebar visible by default
)

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

# ============ CSS (Minimal, Non-Conflicting) ============
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
    }
    
    .main-header {
        text-align: center;
        padding: 1rem 0 0.5rem 0;
    }
    
    .main-header h1 {
        font-size: 2.8rem;
        font-weight: 700;
        letter-spacing: -0.045em;
        color: #1d1d1f;
        margin: 0;
    }
    
    .main-header p {
        font-size: 1.1rem;
        color: #86868b;
        font-weight: 400;
        margin-top: 0.3rem;
    }
    
    /* Style Streamlit buttons to look Apple-like */
    .stButton > button {
        background: #f5f5f7;
        color: #1d1d1f;
        border: 1px solid #d2d2d7;
        border-radius: 18px;
        padding: 1rem;
        font-weight: 500;
        font-size: 0.9rem;
        font-family: 'Inter', sans-serif;
        width: 100%;
        height: auto;
        transition: all 0.2s;
        text-align: left;
        line-height: 1.4;
    }
    
    .stButton > button:hover {
        background: #ffffff;
        border-color: #0071e3;
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
</style>
""", unsafe_allow_html=True)

# ============ SIDEBAR ============
with st.sidebar:
    st.title("⚙️ Settings")
    
    # API Key
    api_key = st.text_input(
        "StepFun API Key",
        type="password",
        help="Get yours from your StepFun dashboard",
        value=st.secrets.get("STEPFUN_API_KEY", "")
    )
    
    # Model Selection
    MODEL_OPTIONS = [
        "step-5-preview",
        "step-1-8k",
        "step-1-32k",
        "step-2-16k",
    ]
    
    model_name = st.selectbox(
        "Model",
        MODEL_OPTIONS,
        index=0,
    )
    
    if api_key:
        st.success("✅ Ready to learn!")
    else:
        st.warning("⚠️ Enter your API key above")
    
    st.divider()
    
    if st.button("🗑️ Clear Conversation"):
        st.session_state.messages = []
        st.rerun()

# ============ FUNCTION TO GET AI RESPONSE ============
def get_ai_response(user_message):
    """Send message to StepFun API and return the response."""
    
    if not api_key:
        return "⚠️ **No API key set.**\n\nPlease open the sidebar (left side) and paste your StepFun API key, then try again."
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=API_BASE_URL
        )
        
        # Build conversation
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        
        for msg in st.session_state.messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add the new user message
        api_messages.append({"role": "user", "content": user_message})
        
        # Call API (non-streaming for reliability)
        response = client.chat.completions.create(
            model=model_name,
            messages=api_messages,
            max_tokens=4000,
            temperature=0.6
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg:
            return "❌ **Invalid API key.** Check your key in the sidebar."
        elif "404" in error_msg:
            return f"❌ **Model not found:** `{model_name}`. Try selecting 'step-1-8k' in the sidebar."
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

# ============ PROJECT SELECTION (When No Messages) ============
if len(st.session_state.messages) == 0 and not st.session_state.pending_start:
    
    st.write("")  # spacing
    st.markdown("##### Choose a project to begin:")
    st.write("")
    
    # Project 1: Topology Optimization
    if st.button(
        "🏗️  Topology Optimization\n\nBuild a working SIMP solver from scratch. Learn Python, FEA, and structural design as you build.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I want to start the topology optimization project. Please give me the project brief and scope."
        st.rerun()
    
    st.write("")
    
    # Project 2: System Design  
    if st.button(
        "📐  System Design\n\nDesign and build real systems. From requirements to architecture to working code.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I want to start the system design project. Please give me the project brief and scope."
        st.rerun()
    
    st.write("")
    
    # Project 3: Custom
    if st.button(
        "💡  Your Own Project\n\nHave an idea? The mentor will guide you through it with industry-level rigor.",
        use_container_width=True
    ):
        st.session_state.pending_start = "I have my own project idea I want to work on. What information do you need from me to get started?"
        st.rerun()
    
    st.write("")
    st.caption("Or type your question in the box below ⬇️")

# ============ HANDLE PENDING START ============
if st.session_state.pending_start:
    # Add as user message
    user_msg = st.session_state.pending_start
    st.session_state.pending_start = None
    
    # Add to history
    st.session_state.messages.append({"role": "user", "content": user_msg})
    
    # Get response
    with st.spinner("Starting your project..."):
        response = get_ai_response(user_msg)
        st.session_state.messages.append({"role": "assistant", "content": response})
    
    st.rerun()

# ============ DISPLAY CHAT HISTORY ============
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ============ CHAT INPUT ============
if prompt := st.chat_input("Type your message here..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = get_ai_response(prompt)
            st.write(response)
    
    st.session_state.messages.append({"role": "assistant", "content": response})

# ============ FOOTER ============
st.write("")
st.caption("Studio — Project-based engineering mentorship")
