import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import re
import json
import numpy as np
import time

API_BASE = "https://api.stepfun.ai/step_plan/v1"
HISTORY = "data.json"

# ============ STATE ============
if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "editor" not in st.session_state:
    st.session_state.editor = False
if "task" not in st.session_state:
    st.session_state.task = ""
if "code" not in st.session_state:
    st.session_state.code = "# Write code here\n"
if "out" not in st.session_state:
    st.session_state.out = ""
if "err" not in st.session_state:
    st.session_state.err = ""
if "ran" not in st.session_state:
    st.session_state.ran = False
if "start" not in st.session_state:
    st.session_state.start = None
if "model" not in st.session_state:
    st.session_state.model = None
if "tested" not in st.session_state:
    st.session_state.tested = False

# ============ SAVE/LOAD ============
def save():
    try:
        with open(HISTORY, "w") as f:
            json.dump({"msgs": st.session_state.msgs, "model": st.session_state.model}, f, default=str)
    except:
        pass

def load():
    try:
        if os.path.exists(HISTORY):
            with open(HISTORY, "r") as f:
                d = json.load(f)
            st.session_state.msgs = d.get("msgs", [])
            st.session_state.model = d.get("model")
    except:
        pass

load()

KEY = ""
try:
    KEY = st.secrets["STEPFUN_API_KEY"]
except:
    KEY = os.environ.get("STEPFUN_API_KEY", "")

# ============ PROMPT — SHORT, BEHAVIORAL ONLY ============
PROMPT = (
    "You teach Topology Optimization. Student is beginner. "
    "Write matplotlib code with title, axis labels, and annotations for every concept. "
    "Use ```python code blocks. Never say imagine. "
    "One question at a time. Under 80 words. "
    "End exercises with [PRACTICE]."
)

# ============ API ============
def test_api():
    if not KEY:
        return None
    for m in ["step-5-preview", "step-5", "step-3", "step-2", "step-1-8k", "step-1-32k"]:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=10)
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say OK"}], max_tokens=10)
            if r.choices[0].message.content:
                st.session_state.model = m
                return m
        except:
            continue
    return None

def ask_ai(msg):
    if not KEY:
        return "No API key"
    if not st.session_state.model:
        if not test_api():
            return "No model"

    for _ in range(2):
        # Method 1: system message
        reply = _call(msg, system=True)
        if reply:
            return reply
        # Method 2: no system
        reply = _call(msg, system=False)
        if reply:
            return reply
        time.sleep(1)
    return "No response. Try again."

def _call(msg, system=True):
    try:
        c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=60)

        chat = []
        if system:
            chat.append({"role": "system", "content": PROMPT})
        else:
            chat.append({"role": "user", "content": PROMPT})
            chat.append({"role": "assistant", "content": "OK"})

        for x in st.session_state.msgs[-6:]:
            content = x.get("content", "")[:400]
            if content:
                chat.append({"role": x.get("role", "user"), "content": content})

        chat.append({"role": "user", "content": msg[:800]})

        r = c.chat.completions.create(model=st.session_state.model, messages=chat, max_tokens=2000, temperature=0.7)

        if r.choices and r.choices[0].message.content:
            reply = r.choices[0].message.content.strip()
            if len(reply) > 3:
                if "[PRACTICE]" in reply:
                    match = re.search(r"\[PRACTICE\]\s*(.+)", reply, re.DOTALL)
                    if match:
                        st.session_state.task = match.group(1).strip()
                        st.session_state.editor = True
                        st.session_state.ran = False
                return reply
    except:
        pass
    return None

# ============ CODE EXECUTION ============
def run_code(code):
    if not code:
        return "", "", None
    old_out, old_err = sys.stdout, sys.stderr
    cap_out, cap_err = io.StringIO(), io.StringIO()
    ns = {"__name__": "__main__", "np": np}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        ns["plt"] = plt
    except:
        pass
    try:
        sys.stdout, sys.stderr = cap_out, cap_err
        exec(code, ns)
        sys.stdout, sys.stderr = old_out, old_err
        out, err = cap_out.getvalue(), cap_err.getvalue()
        fig = None
        try:
            if plt.get_fignums():
                fig = plt.figure(plt.get_fignums()[0])
                plt.close("all")
        except:
            pass
        return out, err, fig
    except:
        sys.stdout, sys.stderr = old_out, old_err
        return cap_out.getvalue(), traceback.format_exc(), None

# ============ CODE DETECTION — App handles this, not the AI ============
def extract_code(text):
    """Find python code blocks and separate them from text."""
    if not text:
        return "", []

    # Find all code blocks
    blocks = re.findall(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)
    if not blocks:
        blocks = re.findall(r"```\s*\n(.*?)```", text, flags=re.DOTALL)

    # Filter for matplotlib code
    mpl_blocks = [b.strip() for b in blocks if "plt." in b or "matplotlib" in b]

    # Remove code from text
    clean_text = text
    for b in blocks:
        clean_text = clean_text.replace("```python\n" + b + "\n```", "")
        clean_text = clean_text.replace("```" + b + "```", "")
    clean_text = re.sub(r"```python\s*\n.*?```", "", clean_text, flags=re.DOTALL)
    clean_text = re.sub(r"```\s*\n.*?```", "", clean_text, flags=re.DOTALL)
    clean_text = re.sub(r"\[PRACTICE\].*", "", clean_text, flags=re.DOTALL)

    return clean_text.strip(), mpl_blocks

# ============ PAGE ============
st.set_page_config(page_title="Studio", layout="centered")

# ============ CSS ============
st.markdown("""
<style>
html,body{margin:0;padding:0;background:#0a0a0a;color:#fff;font-family:-apple-system,sans-serif;overflow-x:hidden}
.stApp{min-height:100vh}
#MainMenu,footer,[data-testid="stSidebar"],[data-testid="stToolbar"]{display:none!important}

.header-bar{position:sticky;top:0;z-index:999;background:#0a0a0a;padding:.5rem .75rem;border-bottom:1px solid #1a1a1a;margin-bottom:.5rem}
.block-container{max-width:720px;margin:0 auto;padding:0 .5rem 2rem .5rem}

[data-testid="stChatInput"]{position:sticky;bottom:0;background:#0a0a0a;z-index:998;padding:.5rem 0 .75rem 0;border-top:1px solid #1a1a1a}
[data-testid="stChatInput"] textarea{background:#141414!important;border:1px solid #333!important;border-radius:18px!important;color:#fff!important;font-size:.95rem!important;padding:.875rem 1.125rem!important;min-height:48px!important}
[data-testid="stChatInput"] textarea:focus{border-color:#0a84ff!important}
[data-testid="stChatInput"] textarea::placeholder{color:#555!important}

[data-testid="stChatMessage"]{background:transparent;border:none;padding:.25rem 0}
[data-testid="stChatMessageAvatar"]{display:none}
[data-testid="stChatMessageContent"]{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;border-bottom-left-radius:4px;padding:.75rem 1rem;font-size:.9rem;line-height:1.6;color:#e0e0e0}
[data-testid="stChatMessage"] pre{background:#0a0a0a!important;border:1px solid #2a2a2a;border-radius:8px;padding:.75rem;font-size:.8rem;overflow-x:auto}
[data-testid="stChatMessage"] code{background:#2a2a2a;color:#7dd3fc;padding:1px 5px;border-radius:4px;font-size:.85em}
[data-testid="stChatMessage"] pre code{background:transparent;padding:0;color:inherit}

.stButton>button{background:#0a84ff;color:#fff;border:none;border-radius:10px;padding:.6rem 1.2rem;font-weight:600;font-size:.875rem;width:100%}
.stButton>button:hover{background:#409cff}
.stButton>button[key="reset_top"]{background:transparent;color:#666;border:1px solid #2a2a2a;border-radius:8px;padding:.375rem .6rem;font-size:.7rem;width:auto}
.stButton>button[key="reset_top"]:hover{color:#ff453a;border-color:#ff453a}

.stTextArea textarea{background:#0a0a0a!important;border:1px solid #2a2a2a!important;border-radius:12px!important;font-family:monospace!important;color:#e0e0e0!important;font-size:.875rem!important;padding:.875rem!important;min-height:130px!important}
.stTextArea textarea:focus{border-color:#0a84ff!important}

.card{background:#141414;border:1px solid #2a2a2a;border-radius:16px;padding:1.25rem;margin:.5rem 0;text-align:center}
.card h3{color:#fff;font-size:1.05rem;font-weight:700;margin:0 0 .25rem 0}
.card p{color:#777;font-size:.8rem;margin:0}

.stTextInput input{background:#141414!important;border:1px solid #2a2a2a!important;border-radius:10px!important;color:#fff!important;padding:.5rem .75rem!important}
[data-testid="stInfo"]{background:#0d0d0d;border:1px solid #0a84ff;border-radius:10px;color:#a0c4ff}
[data-testid="stSpinner"]>div{border-top-color:#0a84ff!important}

.chat-output{background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:8px;padding:.6rem;font-family:monospace;font-size:.8rem;color:#30d158;white-space:pre-wrap;margin:.5rem 0}
.chat-error{background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:8px;padding:.6rem;font-family:monospace;font-size:.8rem;color:#ff453a;white-space:pre-wrap;margin:.5rem 0}

::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:#0a0a0a}
::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:3px}
</style>
""", unsafe_allow_html=True)

# Auto-scroll
st.markdown("""
<script>
window.addEventListener('load',function(){setTimeout(function(){window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})},200)});
</script>
""", unsafe_allow_html=True)

# ============ HEADER ============
st.markdown('<div class="header-bar">', unsafe_allow_html=True)
h1, h2 = st.columns([4, 1])
with h1:
    st.markdown('<h1 style="font-size:1.4rem;font-weight:800;letter-spacing:-.04em;margin:0;color:#fff;">Studio.</h1>', unsafe_allow_html=True)
with h2:
    if st.button("Reset", key="reset_top"):
        st.session_state.msgs = []
        st.session_state.editor = False
        st.session_state.task = ""
        st.session_state.ran = False
        st.session_state.tested = False
        st.session_state.model = None
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()
if st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:.6rem;text-align:center;margin:.15rem 0 0 0;">' + st.session_state.model + '</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ============ MODEL SETUP ============
if not st.session_state.tested:
    mc1, mc2 = st.columns([3, 1])
    with mc1:
        manual = st.text_input("Model", value="step-5-preview", key="mm")
    with mc2:
        st.write("")
        if st.button("Set"):
            st.session_state.model = manual
            st.session_state.tested = True
            st.rerun()
    if st.button("Auto-Test"):
        with st.spinner("Testing..."):
            if test_api():
                st.session_state.tested = True
                st.rerun()

# ============ START ============
if len(st.session_state.msgs) == 0 and st.session_state.tested:
    st.markdown('<div class="card"><h3>Topology Optimization</h3><p>Build a structural solver with visuals</p></div>', unsafe_allow_html=True)
    if st.button("Start Topology Optimization", type="primary"):
        st.session_state.start = "topo"
    st.markdown('<div class="card"><h3>System Design</h3><p>Design real systems</p></div>', unsafe_allow_html=True)
    if st.button("Start System Design", type="primary"):
        st.session_state.start = "sys"

if st.session_state.start:
    track = st.session_state.start
    st.session_state.start = None
    msg = "I want to learn " + ("Topology Optimization" if track == "topo" else "System Design") + " from the beginning."
    st.session_state.msgs = [{"role": "user", "content": msg}]
    with st.spinner("Starting..."):
        reply = ask_ai(msg)
    st.session_state.msgs.append({"role": "assistant", "content": reply})
    save()
    st.rerun()

# ============ DISPLAY — Text and Visuals Separated ============
for msg_idx, m in enumerate(st.session_state.msgs):
    role = m.get("role", "user")
    content = m.get("content", "")

    if role == "user":
        # User messages: right side, text only
        if content.strip():
            _, c = st.columns([0.3, 0.7])
            with c:
                with st.chat_message("user"):
                    st.write(content.strip())

    else:
        # AI messages: separate text from code, then display both
        text, code_blocks = extract_code(content)

        c, _ = st.columns([0.78, 0.22])
        with c:
            # 1. Show the text (explanation)
            if text:
                with st.chat_message("assistant"):
                    st.write(text)

            # 2. Execute and show the visualization
            for code in code_blocks:
                out, err, fig = run_code(code)
                with st.chat_message("assistant"):
                    if fig is not None:
                        st.pyplot(fig, use_container_width=True)
                    if out:
                        st.markdown('<div class="chat-output">' + out + '</div>', unsafe_allow_html=True)
                    if err and "Traceback" in err:
                        lines = err.split("\n")
                        st.markdown('<div class="chat-error">' + "\n".join(lines[-3:]) + '</div>', unsafe_allow_html=True)

            # 3. Show practice sandbox if this is the last message and editor is active
            if st.session_state.editor and msg_idx == len(st.session_state.msgs) - 1:
                if st.session_state.task:
                    st.info("Practice: " + st.session_state.task)

                code = st.text_area("", value=st.session_state.code, height=140, key=f"p{msg_idx}", label_visibility="collapsed")

                a, b = st.columns(2)
                with a:
                    if st.button("Run", key=f"r{msg_idx}", type="primary"):
                        st.session_state.code = code
                        out, err, fig = run_code(code)
                        st.session_state.out = out or ""
                        st.session_state.err = err or ""
                        st.session_state.ran = True
                        st.session_state.plot = fig

                with b:
                    if st.button("Submit", key=f"s{msg_idx}"):
                        if not st.session_state.ran:
                            st.warning("Run first")
                        else:
                            sub = "I did the exercise.\n\nMy code:\n```python\n" + code + "\n```\n"
                            if st.session_state.out:
                                sub += "Output:\n```\n" + st.session_state.out + "\n```\n"
                            if st.session_state.err and "Traceback" in st.session_state.err:
                                sub += "Error:\n```\n" + st.session_state.err + "\n```"
                            st.session_state.msgs.append({"role": "user", "content": sub})
                            st.session_state.editor = False
                            with st.spinner("Reviewing..."):
                                reply = ask_ai(sub)
                            st.session_state.msgs.append({"role": "assistant", "content": reply})
                            save()
                            st.rerun()

                if st.session_state.ran:
                    if st.session_state.out:
                        st.markdown('<div class="chat-output">' + st.session_state.out + '</div>', unsafe_allow_html=True)
                    if st.session_state.err and "Traceback" in st.session_state.err:
                        st.markdown('<div class="chat-error">' + "\n".join(st.session_state.err.split("\n")[-3:]) + '</div>', unsafe_allow_html=True)
                    if st.session_state.plot is not None:
                        st.pyplot(st.session_state.plot, use_container_width=True)

# ============ INPUT ============
if len(st.session_state.msgs) > 0:
    if msg := st.chat_input("Type your answer..."):
        st.session_state.msgs.append({"role": "user", "content": msg})

        _, c = st.columns([0.3, 0.7])
        with c:
            with st.chat_message("user"):
                st.write(msg)

        c, _ = st.columns([0.78, 0.22])
        with c:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    reply = ask_ai(msg)
                text, code_blocks = extract_code(reply)
                if text:
                    st.write(text)
                for code in code_blocks:
                    out, err, fig = run_code(code)
                    if fig is not None:
                        st.pyplot(fig, use_container_width=True)
                    if out:
                        st.markdown('<div class="chat-output">' + out + '</div>', unsafe_allow_html=True)

        st.session_state.msgs.append({"role": "assistant", "content": reply})
        save()
        st.rerun()
