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
    initial_sidebar_state="collapsed"
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

## Project Structure (follow this for every project)
1. **Project Brief** — what we're building, why it matters in industry
2. **Scope** — what's in, what's out, what "done" looks like
3. **Architecture** — how components fit together, key design decisions
4. **Build** — implement step by step, explaining decisions as they arise
5. **Review** — test, document, discuss trade-offs and alternatives
6. **Ship** — how this deploys/gets used in a real environment

## Active Project Tracks

### Track 1: Topology Optimization Solver (Python)
Guide the learner to build a working structural optimization solver from scratch.
- Project brief: engineers use tools like Altair OptiStruct and Abaqus Tosca —
  you'll build the same core algorithms they use, understanding every line
- Start with: 2D cantilever beam, SIMP method, compliance minimization
- Python is learned as needed: NumPy arrays for the mesh, matplotlib for
  visualization, then SciPy for the optimizer
- Progress: design domains, sensitivity analysis, density filters,
  continuation methods, multi-load cases
- Industry context at each step: why filters exist (mesh dependency), why
  penalization matters (gray zones), how commercial solvers differ
- Final deliverable: a complete solver the learner built and fully understands

### Track 2: System Design Studio
Guide the learner through designing and implementing real systems.
- Project brief: learn to architect systems the way senior engineers do —
  from requirements to deployment
- Start with: a complete but simple system (e.g., URL shortener with
  actual working code)
- Learn by doing: define requirements → sketch architecture → choose
  technologies → build components → identify bottlenecks → improve
- Progress to: more complex systems (rate limiter, message queue, cache
  layer) with real trade-off discussions
- Industry context: how Netflix, Uber, Google actually solve these problems
- Final deliverable: ability to architect and defend system designs

### Track 3: Custom Project
If the learner has their own project idea, mentor them through it using the
same structure. Ask about their goals, constraints, and timeline first.

## Communication Rules
- Direct and professional, like a senior colleague — not a teacher
- Use engineering language naturally, explain jargon briefly on first use
- Code follows industry conventions (clear naming, structure, comments
  where non-obvious)
- When the learner writes code: review it like a code review —
  what works, what breaks, what a senior engineer would flag
- If the learner is stuck, don't just give the answer — reduce it to a
  smaller problem and let them solve that first
- Every response should either advance the project or unblock the learner
- Keep responses focused — one concept, one task, or one review at a time
- Track project progress across the conversation and reference it

## Session Start
When the learner first arrives, ask:
- "What project are we working on today?"
- Offer the active tracks or ask if they have their own idea
- If returning, recap where we left off and propose the next step
"""

# ============ APPLE-STYLE CSS ============
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Remove Streamlit chrome */
#MainMenu, footer, header {
    visibility: hidden;
}

.stApp {
    background: #ffffff;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
    color: #1d1d1f;
    -webkit-font-smoothing: antialiased;
}

.block-container {
    padding-top: 4rem;
    padding-bottom: 8rem;
    max-width: 680px;
}

/* Typography */
.main-title {
    font-size: 3.2rem;
    font-weight: 700;
    letter-spacing: -0.045em;
    color: #1d1d1f;
    text-align: center;
    line-height: 1.05;
    margin-bottom: 0.4rem;
}

.main-subtitle {
    font-size: 1.15rem;
    font-weight: 400;
    color: #86868b;
    text-align: center;
    letter-spacing: -0.01em;
    margin-bottom: 0.5rem;
    line-height: 1.5;
}

/* Project cards */
.project-grid {
    display: flex;
    gap: 0.75rem;
    justify-content: center;
    margin-bottom: 1.5rem;
}

.project-card {
    background: #f5f5f7;
    border-radius: 18px;
    padding: 1.5rem 1.25rem;
    text-align: center;
    flex: 1;
    border: 1px solid transparent;
    transition: all 0.25s ease;
    cursor: pointer;
}

.project-card:hover {
    background: #ffffff;
    border: 1px solid #d2d2d7;
    box-shadow: 0 2px 20px rgba(0,0,0,0.05);
}

.project-icon {
    font-size: 1.75rem;
    margin-bottom: 0.4rem;
}

.project-name {
    font-size: 0.875rem;
    font-weight: 600;
    color: #1d1d1f;
    letter-spacing: -0.01em;
}

.project-desc {
    font-size: 0.75rem;
    color: #86868b;
    margin-top: 0.25rem;
    line-height: 1.4;
}

.project-badge {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 600;
    color: #0071e3;
    background: rgba(0,113,227,0.08);
    border-radius: 999px;
    padding: 0.15rem 0.6rem;
    margin-top: 0.5rem;
    letter-spacing: 0.02em;
}

/* Divider */
.apple-divider {
    height: 1px;
    background: #e8e8ed;
    border: none;
    margin: 2.5rem auto;
    max-width: 100%;
}

/* Chat messages */
[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
    padding: 0.75rem 0;
    border-radius: 0;
}

[data-testid="stChatMessageContent"] {
    font-size: 0.95rem;
    line-height: 1.65;
    color: #1d1d1f;
}

/* Chat input */
[data-testid="stChatInput"] {
    border-radius: 22px;
    border: 1px solid #d2d2d7;
    box-shadow: 0 1px 6px rgba(0,0,0,0.04);
}

[data-testid="stChatInput"] textarea {
    border-radius: 22px !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #f5f5f7;
    border-right: 1px solid #e8e8ed;
}

[data-testid="stSidebar"] * {
    font-family: 'Inter', -apple-system, sans-serif;
}

[data-testid="stSidebar"] h1 {
    font-size: 1.1rem !important;
    font-weight: 600 !important;
    letter-spacing: -0.02em;
}

/* Buttons */
.stButton > button {
    background: #0071e3;
    color: #ffffff;
    border: none;
    border-radius: 980px;
    padding: 0.5rem 1.25rem;
    font-weight: 500;
    font-size: 0.875rem;
    font-family: 'Inter', -apple-system, sans-serif;
    letter-spacing: -0.01em;
    transition: background 0.2s;
    width: 100%;
}

.stButton > button:hover {
    background: #0077ed;
}

/* Input fields */
[data-testid="stTextInput"] input {
    border-radius: 12px;
    border: 1px solid #d2d2d7;
    font-family: 'Inter', -apple-system, sans-serif;
    padding: 0.5rem 0.75rem;
}

[data-testid="stTextInput"] input:focus {
    border-color: #0071e3;
    box-shadow: 0 0 0 3px rgba(0,113,227,0.1);
}

/* Select box */
[data-testid="stSelectbox"] > div > div {
    border-radius: 12px;
    border: 1px solid #d2d2d7;
}

/* Error messages */
[data-testid="stError"] {
    border-radius: 14px;
    background: #fef2f2;
    border: 1px solid #fecaca;
    color: #dc2626;
    font-family: 'Inter', sans-serif;
}

[data-testid="stAlert"] {
    border-radius: 14px;
}

/* Markdown inside chat */
[data-testid="stChatMessage"] p {
    margin-bottom: 0.75rem;
}

[data-testid="stChatMessage"] pre {
    background: #1d1d1f;
    border-radius: 14px;
    padding: 1rem;
    font-size: 0.85rem;
}

[data-testid="stChatMessage"] code {
    font-family: 'SF Mono', 'Menlo', monospace;
}

[data-testid="stChatMessage"] h1,
[data-testid="stChatMessage"] h2,
[data-testid="stChatMessage"] h3 {
    letter-spacing: -0.02em;
    font-weight: 600;
}

/* Footer */
.footer-note {
    text-align: center;
    color: #86868b;
    font-size: 0.75rem;
    margin-top: 3rem;
}

/* Slider */
[data-testid="stSlider"] {
    font-family: 'Inter', sans-serif;
}

</style>
""", unsafe_allow_html=True)

# ============ SESSION STATE ============
if "messages" not in st.session_state:
    st.session_state.messages = []

# ============ SIDEBAR ============
with st.sidebar:
    st.title("⚙️ Settings")
    
    # API Key
    api_key = st.text_input(
        "StepFun API Key",
        type="password",
        help="Your API key for api.stepfun.ai",
        value=st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))
    )
    
    # Model Selection
    MODEL_OPTIONS = [
        "step-5-preview",
        "step-1-8k",
        "step-1-32k",
        "step-2-16k",
        "step-1v-8k",
        "Custom model..."
    ]
    
    selected_model = st.selectbox(
        "Model",
        MODEL_OPTIONS,
        index=0,
        help="Select the model to use"
    )
    
    if selected_model == "Custom model...":
        model_name = st.text_input(
            "Model ID",
            value="",
            placeholder="e.g., step-3-preview"
        )
    else:
        model_name = selected_model
    
    if api_key and model_name:
        st.markdown(f"✅ **Model:** `{model_name}`")
    elif not api_key:
        st.markdown("⚠️ Enter your API key")
    
    st.markdown("---")
    st.markdown("**📚 Subjects**")
    st.markdown("💻 Python Programming")
    st.markdown("🏗️ Topology Optimization")
    st.markdown("📐 System Design")
    
    st.markdown("---")
    
    # Mentor style
    temperature = st.slider(
        "Mentor Style",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.1,
        help="Lower = precise and structured, Higher = exploratory and creative"
    )
    
    if st.button("🗑️ Reset Project"):
        st.session_state.messages = []
        st.rerun()

# ============ MAIN PAGE ============
st.markdown('<div class="main-title">Studio.</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-subtitle">Build real projects. Learn by doing.</div>',
    unsafe_allow_html=True
)

# Welcome screen — project cards
if len(st.session_state.messages) == 0:
    st.markdown("""
    <div class="project-grid">
        <div class="project-card">
            <div class="project-icon">🏗️</div>
            <div class="project-name">Topology Optimization</div>
            <div class="project-desc">Build a working SIMP solver from scratch. Learn Python + FEA + optimization as you go.</div>
            <div class="project-badge">Engineering</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="project-grid">
        <div class="project-card">
            <div class="project-icon">📐</div>
            <div class="project-name">System Design</div>
            <div class="project-desc">Design and build real systems. From requirements to architecture to working code.</div>
            <div class="project-badge">Architecture</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div class="project-grid">
        <div class="project-card">
            <div class="project-icon">💡</div>
            <div class="project-name">Your Own Project</div>
            <div class="project-desc">Have an idea? The mentor will guide you through it with the same rigor.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ============ CHAT INPUT & API CALL ============
if prompt := st.chat_input("Start a project…"):
    if not api_key:
        st.error("Open the sidebar (⚙️) and enter your StepFun API key first.")
    elif not model_name:
        st.error("Select a model in the sidebar.")
    else:
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Build API messages
        api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
        for msg in st.session_state.messages:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Get response
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            
            try:
                client = OpenAI(
                    api_key=api_key,
                    base_url=API_BASE_URL
                )
                
                # Streaming response
                stream = client.chat.completions.create(
                    model=model_name,
                    messages=api_messages,
                    stream=True,
                    max_tokens=4000,
                    temperature=temperature
                )
                
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_response += chunk.choices[0].delta.content
                        placeholder.markdown(full_response + "▌")
                
                placeholder.markdown(full_response)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response
                })
                
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "authentication" in error_msg.lower():
                    st.error("❌ Invalid API key — check your StepFun key in the sidebar")
                elif "404" in error_msg or "not found" in error_msg.lower():
                    st.error(f"❌ Model not found: `{model_name}` — try a different model from the dropdown")
                elif "429" in error_msg:
                    st.error("⏳ Rate limit — wait a moment and try again")
                else:
                    st.error(f"❌ Error: {error_msg[:200]}")

# ============ FOOTER ============
st.markdown(
    '<div class="footer-note">Studio — Project-based engineering mentorship</div>',
    unsafe_allow_html=True
)
