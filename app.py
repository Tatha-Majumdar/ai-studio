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
API_BASE = "https://api.stepfun.ai/step_plan/v1"
HISTORY = "data.json"

# ============ INIT ============
if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "editor" not in st.session_state:
    st.session_state.editor = False
if "task" not in st.session_state:
    st.session_state.task = ""
if "code" not in st.session_state:
    st.session_state.code = "# Write code here\nprint('Hello')"
if "out" not in st.session_state:
    st.session_state.out = ""
if "err" not in st.session_state:
    st.session_state.err = ""
if "ran" not in st.session_state:
    st.session_state.ran = False
if "plot" not in st.session_state:
    st.session_state.plot = None
if "start" not in st.session_state:
    st.session_state.start = None
if "model" not in st.session_state:
    st.session_state.model = "step-1-8k"

# ============ SAVE / LOAD ============
def save():
    try:
        d = {
            "msgs": st.session_state.msgs,
            "model": st.session_state.model,
        }
        with open(HISTORY, "w") as f:
            json.dump(d, f, default=str)
    except:
        pass

def load():
    try:
        if os.path.exists(HISTORY):
            with open(HISTORY, "r") as f:
                d = json.load(f)
            if "msgs" in d:
                st.session_state.msgs = d["msgs"]
            if "model" in d:
                st.session_state.model = d["model"]
    except:
        pass

load()

# ============ API ============
KEY = ""
try:
    KEY = st.secrets["STEPFUN_API_KEY"]
except:
    KEY = os.environ.get("STEPFUN_API_KEY", "")

PROMPT = (
    "You are a senior engineering mentor. You teach Topology Optimization and System Design. "
    "The student may have zero coding experience. "
    "RULES: "
    "1. Ask one question then STOP and wait. Never combine question with lesson. "
    "2. Never say imagine or visualize. Always show with code. "
    "3. To show a visual, write code the student can run. "
    "4. To give practice, end message with [PRACTICE] then the task. "
    "5. Keep responses under 150 words. "
    "6. One concept at a time. "
    "7. When student answers, then teach next concept. "
    "8. Start by asking about their coding experience."
)

def ask_ai(msg):
    if not KEY:
        return "No API key found. Go to Settings > Secrets and add STEPFUN_API_KEY."

    models = [st.session_state.model, "step-1-8k", "step-1-32k", "step-2-16k"]

    for m in models:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE)
            chat = [{"role": "system", "content": PROMPT}]

            for x in st.session_state.msgs:
                chat.append({"role": x.get("role", "user"), "content": x.get("content", "")})

            chat.append({"role": "user", "content": msg})

            r = c.chat.completions.create(
                model=m,
                messages=chat,
                max_tokens=3000,
                temperature=0.6
            )

            reply = r.choices[0].message.content

            if reply and len(reply.strip()) > 5:
                st.session_state.model = m
                # Check for practice marker
                if "[PRACTICE]" in reply:
                    match = re.search(r'\[PRACTICE\]\s*(.+)', reply, re.DOTALL)
                    if match:
                        st.session_state.task = match.group(1).strip()
                        st.session_state.editor = True
                        st.session_state.ran = False
                        st.session_state.out = ""
                        st.session_state.err = ""
                return reply
        except:
            continue

    return "Could not connect. Check your API key and internet."

# ============ RUN CODE ============
def run_code(code):
    if not code:
        return "", "No code", None

    old_out = sys.stdout
    old_err = sys.stderr
    cap_out = io.StringIO()
    cap_err = io.StringIO()

    ns = {"__name__": "__main__"}

    try:
        import numpy as np
        ns['np'] = np
    except:
        pass
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        ns['plt'] = plt
    except:
        pass

    try:
        sys.stdout = cap_out
        sys.stderr = cap_err
        exec(code, ns)
        sys.stdout = old_out
        sys.stderr = old_err

        out = cap_out.getvalue()
        err = cap_err.getvalue()

        fig = None
        try:
            nums = plt.get_fignums()
            if nums:
                fig = plt.figure(nums[0])
                plt.close('all')
        except:
            pass

        return out, err, fig

    except Exception:
        sys.stdout = old_out
        sys.stderr = old_err
        out = cap_out.getvalue()
        err = traceback.format_exc()
        return out, err, None

# ============ CLEAN TEXT ============
def clean(t):
    if not t:
        return ""
    t = re.sub(r'\[PRACTICE\].*', '', t, flags=re.DOTALL)
    return t.strip()

# ============ PAGE ============
st.set_page_config(page_title="Studio", layout="centered")

# ============ STYLE ============
st.markdown("""
<style>
    .stApp {
        background: #0a0a0a;
        color: #fff;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    [data-testid="stSidebar"] {
        display: none;
    }

    .block-container {
        max-width: 700px;
        padding-top: 1rem;
        padding-bottom: 5rem;
    }

    /* Title */
    .title {
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        color: #fff;
        letter-spacing: -0.04em;
        padding: 0.5rem 0;
    }

    .subtitle {
        text-align: center;
        font-size: 0.85rem;
        color: #666;
        margin-bottom: 1.5rem;
    }

    /* Chat bubbles */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        padding: 0.25rem 0;
    }

    [data-testid="stChatMessageAvatar"] {
        display: none;
    }

    [data-testid="stChatMessageContent"] {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        border-radius: 16px;
        border-bottom-left-radius: 4px;
        padding: 0.8rem 1rem;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #e0e0e0;
    }

    [data-testid="stChatMessage"] pre {
        background: #0a0a0a;
        border: 1px solid #2a2a2a;
        border-radius: 8px;
        padding: 0.8rem;
        font-size: 0.8rem;
    }

    [data-testid="stChatMessage"] code {
        background: #2a2a2a;
        color: #7dd3fc;
        padding: 2px 5px;
        border-radius: 4px;
        font-size: 0.85em;
    }

    /* Chat input - bigger and cleaner */
    [data-testid="stChatInput"] {
        padding: 0.5rem 0;
    }

    [data-testid="stChatInput"] textarea {
        background: #141414 !important;
        border: 1px solid #333 !important;
        border-radius: 20px !important;
        color: #fff !important;
        font-size: 1rem !important;
        font-family: -apple-system, sans-serif !important;
        padding: 1rem 1.25rem !important;
        min-height: 56px !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3) !important;
    }

    [data-testid="stChatInput"] textarea:focus {
        border-color: #0a84ff !important;
        box-shadow: 0 0 0 3px rgba(10,132,255,0.15) !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: #555 !important;
    }

    /* Buttons */
    .stButton > button {
        background: #0a84ff;
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        font-family: -apple-system, sans-serif;
        width: 100%;
        transition: all 0.15s;
    }

    .stButton > button:hover {
        background: #409cff;
    }

    .stButton > button:active {
        background: #0868cc;
    }

    /* Code editor */
    .stTextArea textarea {
        background: #0a0a0a !important;
        border: 1px solid #1a1a1a !important;
        border-radius: 12px !important;
        font-family: 'SF Mono', 'Menlo', monospace !important;
        color: #e0e0e0 !important;
        font-size: 0.9rem !important;
        line-height: 1.6 !important;
        padding: 1rem !important;
        min-height: 160px !important;
    }

    .stTextArea textarea:focus {
        border-color: #0a84ff !important;
    }

    /* Cards */
    .card {
        background: #141414;
        border: 1px solid #2a2a2a;
        border-radius: 16px;
        padding: 1.25rem;
        margin: 0.5rem 0;
        text-align: center;
    }

    .card h3 {
        color: #fff;
        font-size: 1.1rem;
        font-weight: 700;
        margin: 0 0 0.25rem 0;
    }

    .card p {
        color: #777;
        font-size: 0.8rem;
        margin: 0;
    }

    /* Output */
    .good {
        background: #0d0d0d;
        border: 1px solid rgba(48,209,88,0.3);
        border-radius: 10px;
        padding: 0.8rem;
        font-family: monospace;
        font-size: 0.85rem;
        color: #30d158;
        white-space: pre-wrap;
        margin: 0.5rem 0;
    }

    .bad {
        background: #1a0d0d;
        border: 1px solid rgba(255,69,58,0.3);
        border-radius: 10px;
        padding: 0.8rem;
        font-family: monospace;
        font-size: 0.85rem;
        color: #ff453a;
        white-space: pre-wrap;
        margin: 0.5rem 0;
    }

    .label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #0a84ff;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin: 1rem 0 0.5rem 0;
    }

    hr {
        border: none;
        height: 1px;
        background: #1a1a1a;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============ UI ============

# Title
st.markdown('<div class="title">Studio.</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Learn Engineering. Build Real Things.</div>', unsafe_allow_html=True)

# Status
if KEY:
    st.markdown('<p style="color:#30d158;font-size:0.7rem;text-align:center;margin:0 0 1rem 0;">Connected</p>', unsafe_allow_html=True)
else:
    st.markdown('<p style="color:#ff453a;font-size:0.7rem;text-align:center;margin:0 0 1rem 0;">No API Key - Add in Secrets</p>', unsafe_allow_html=True)

# ============ START ============
if len(st.session_state.msgs) == 0:

    st.markdown("""
    <div class="card">
        <h3>Topology Optimization</h3>
        <p>Build a structural solver from scratch</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Start Topology Optimization", type="primary"):
        st.session_state.start = "topo"

    st.markdown("""
    <div class="card">
        <h3>System Design</h3>
        <p>Design and build real systems</p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Start System Design", type="primary"):
        st.session_state.start = "sys"

# ============ HANDLE START ============
if st.session_state.start:
    track = st.session_state.start
    st.session_state.start = None

    if track == "topo":
        msg = "I want to learn Topology Optimization from the very beginning."
    else:
        msg = "I want to learn System Design from the very beginning."

    st.session_state.msgs = [{"role": "user", "content": msg}]

    with st.spinner("Starting..."):
        reply = ask_ai(msg)

    st.session_state.msgs.append({"role": "assistant", "content": reply})
    save()
    st.rerun()

# ============ SHOW CHAT ============
for m in st.session_state.msgs:
    role = m.get("role", "user")
    text = clean(m.get("content", ""))

    if not text:
        continue

    if role == "user":
        _, c = st.columns([0.3, 0.7])
        with c:
            with st.chat_message("user"):
                st.write(text)
    else:
        c, _ = st.columns([0.75, 0.25])
        with c:
            with st.chat_message("assistant"):
                st.write(text)

# ============ CODE SANDBOX ============
if st.session_state.editor:

    st.markdown('<div class="label">Practice</div>', unsafe_allow_html=True)

    if st.session_state.task:
        st.info(st.session_state.task)

    code = st.text_area(
        "code",
        value=st.session_state.code,
        height=180,
        key="editor_box",
        label_visibility="collapsed"
    )

    a, b = st.columns(2)

    with a:
        if st.button("Run", type="primary"):
            st.session_state.code = code
            with st.spinner("Running..."):
                out, err, fig = run_code(code)
                st.session_state.out = out or ""
                st.session_state.err = err or ""
                st.session_state.ran = True
                st.session_state.plot = fig

    with b:
        if st.button("Submit"):
            if not st.session_state.ran:
                st.warning("Run first, then submit.")
            else:
                sub = "I did the exercise.\n\nMy code:\n```python\n" + code + "\n```\n"

                if st.session_state.out:
                    sub += "Output:\n```\n" + st.session_state.out + "\n```\n"

                if st.session_state.err and "Traceback" in st.session_state.err:
                    sub += "Error:\n```\n" + st.session_state.err + "\n```"
                else:
                    sub += "Please review."

                st.session_state.msgs.append({"role": "user", "content": sub})
                st.session_state.editor = False

                with st.spinner("Reviewing..."):
                    reply = ask_ai(sub)

                st.session_state.msgs.append({"role": "assistant", "content": reply})
                save()
                st.rerun()

    if st.session_state.ran:
        if st.session_state.out:
            st.markdown('<div class="good">' + st.session_state.out + '</div>', unsafe_allow_html=True)

        if st.session_state.err and "Traceback" in st.session_state.err:
            lines = st.session_state.err.split("\n")
            short = "\n".join(lines[-4:])
            st.markdown('<div class="bad">' + short + '</div>', unsafe_allow_html=True)

    if st.session_state.plot is not None:
        st.markdown('<div class="label">Plot</div>', unsafe_allow_html=True)
        try:
            st.pyplot(st.session_state.plot, use_container_width=True)
        except:
            pass

# ============ INPUT ============
if len(st.session_state.msgs) > 0:
    if msg := st.chat_input("Type your answer here..."):
        st.session_state.msgs.append({"role": "user", "content": msg})

        _, c = st.columns([0.3, 0.7])
        with c:
            with st.chat_message("user"):
                st.write(msg)

        c, _ = st.columns([0.75, 0.25])
        with c:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = ask_ai(msg)
                st.write(clean(reply))

        st.session_state.msgs.append({"role": "assistant", "content": reply})
        save()

# ============ FOOTER ============
st.markdown("---")

_, mid, _ = st.columns([1, 1, 1])
with mid:
    if st.button("Reset"):
        st.session_state.msgs = []
        st.session_state.editor = False
        st.session_state.task = ""
        st.session_state.ran = False
        st.session_state.out = ""
        st.session_state.err = ""
        st.session_state.plot = None
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()
