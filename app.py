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

if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "editor" not in st.session_state:
    st.session_state.editor = False
if "task" not in st.session_state:
    st.session_state.task = ""
if "code" not in st.session_state:
    st.session_state.code = "print('Hello')"
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
    st.session_state.model = None
if "tested" not in st.session_state:
    st.session_state.tested = False

def save():
    try:
        d = {"msgs": st.session_state.msgs, "model": st.session_state.model}
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

KEY = ""
try:
    KEY = st.secrets["STEPFUN_API_KEY"]
except:
    KEY = os.environ.get("STEPFUN_API_KEY", "")

PROMPT = (
    "You are an engineering mentor for Topology Optimization and System Design. Student is a beginner. "
    "IMPORTANT: When you write code, ALWAYS wrap it in triple backticks with python tag. "
    "Format: ```python\\n[your code here]\\n``` "
    "Never write code outside of these markers. "
    "RULES: Show matplotlib code in code blocks, then explain. Never say imagine. "
    "Under 100 words of text. Ask one question then stop. "
    "Use [PRACTICE] for exercises. Start with coding experience question."
)

def test_api():
    if not KEY:
        return None, "No API key"
    models = ["step-5-preview", "step-5", "step-3", "step-2", "step-1-8k", "step-1-32k"]
    for m in models:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=10)
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say OK"}], max_tokens=10)
            if r.choices[0].message.content:
                if not st.session_state.model:
                    st.session_state.model = m
                return m, "OK"
        except:
            continue
    return None, "No model"

def ask_ai(msg):
    if not KEY:
        return "No API key"
    if not st.session_state.model:
        model, _ = test_api()
        if not model:
            return "No model"

    for attempt in range(3):
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=60)
            chat = [{"role": "system", "content": PROMPT}]
            for x in st.session_state.msgs[-10:]:
                content = x.get("content", "")[:1500]
                if content:
                    chat.append({"role": x.get("role", "user"), "content": content})
            chat.append({"role": "user", "content": msg[:1500]})

            r = c.chat.completions.create(model=st.session_state.model, messages=chat, max_tokens=2000, temperature=0.7)

            if r.choices and r.choices[0].message.content:
                reply = r.choices[0].message.content.strip()
                if len(reply) > 5:
                    if "[PRACTICE]" in reply:
                        match = re.search(r"\[PRACTICE\]\s*(.+)", reply, re.DOTALL)
                        if match:
                            st.session_state.task = match.group(1).strip()
                            st.session_state.editor = True
                            st.session_state.ran = False
                    return reply
            time.sleep(1)
        except:
            time.sleep(2)
    return "Could not get response. Try again."

def run_code(code):
    if not code:
        return "", "No code", None
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
            nums = plt.get_fignums()
            if nums:
                fig = plt.figure(nums[0])
                plt.close("all")
        except:
            pass
        return out, err, fig
    except:
        sys.stdout, sys.stderr = old_out, old_err
        return cap_out.getvalue(), traceback.format_exc(), None

def clean(t):
    if not t:
        return ""
    return re.sub(r"\[PRACTICE\].*", "", t, flags=re.DOTALL).strip()

def find_matplotlib_code(text):
    """Find ALL matplotlib code in text, regardless of formatting."""
    if not text:
        return []

    code_blocks = []

    # Method 1: Proper ```python blocks
    pattern1 = r"```python\s*\n(.*?)```"
    matches1 = re.findall(pattern1, text, flags=re.DOTALL)
    for m in matches1:
        if "plt." in m or "matplotlib" in m or "pyplot" in m:
            code_blocks.append(m.strip())

    # Method 2: ``` blocks without python tag
    if not code_blocks:
        pattern2 = r"```\s*\n(.*?)```"
        matches2 = re.findall(pattern2, text, flags=re.DOTALL)
        for m in matches2:
            if "plt." in m or "matplotlib" in m or "import" in m:
                code_blocks.append(m.strip())

    # Method 3: Find raw code without backticks
    if not code_blocks:
        lines = text.split("\n")
        code_lines = []
        collecting = False

        for line in lines:
            stripped = line.strip()
            # Start collecting when we see an import
            if stripped.startswith("import ") or stripped.startswith("from "):
                if "matplotlib" in stripped or "numpy" in stripped:
                    collecting = True
                    code_lines.append(stripped)
                    continue

            # Continue collecting if we're in code mode
            if collecting:
                # Stop if we hit a sentence (not code)
                if stripped and not stripped.startswith(("#", "plt.", "np.", "print(", "fig", "ax", "import", "from", "x ", "y ")) and "." not in stripped[:5] and "plt" not in stripped:
                    if len(stripped) > 0 and stripped[0].isupper() and not stripped.startswith("plt"):
                        collecting = False
                        if code_lines:
                            code_blocks.append("\n".join(code_lines))
                            code_lines = []
                        continue

                # It looks like code
                if stripped:
                    code_lines.append(stripped)

        # Don't forget the last block
        if code_lines and len(code_lines) > 2:
            code_text = "\n".join(code_lines)
            if "plt." in code_text or "matplotlib" in code_text:
                code_blocks.append(code_text)

    return code_blocks

def execute_and_show(code, key_prefix=""):
    """Execute code and show results inline."""

    with st.spinner("Running..."):
        out, err, fig = run_code(code)

    if out:
        st.markdown('<div style="background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:10px;padding:.75rem;font-family:monospace;font-size:.8rem;color:#30d158;white-space:pre-wrap;margin:.5rem 0;">' + out + '</div>', unsafe_allow_html=True)

    if fig is not None:
        st.markdown('<div style="background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:.5rem;margin:.75rem 0;">', unsafe_allow_html=True)
        st.pyplot(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if err and "Traceback" in err:
        lines = err.split("\n")
        short = "\n".join(lines[-4:])
        st.markdown('<div style="background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:10px;padding:.75rem;font-family:monospace;font-size:.8rem;color:#ff453a;white-space:pre-wrap;margin:.5rem 0;">' + short + '</div>', unsafe_allow_html=True)

st.set_page_config(page_title="Studio", layout="centered")

st.markdown("""
<style>
html,body{margin:0;padding:0;height:100vh;overflow:hidden;background:#0a0a0a;color:#fff;font-family:-apple-system,sans-serif}
.stApp{height:100vh;overflow:hidden}
#MainMenu,footer,header,[data-testid="stSidebar"],[data-testid="stToolbar"]{display:none!important}
.block-container{max-width:720px;height:100vh;display:flex;flex-direction:column;overflow:hidden;padding:0!important;margin:0 auto}

.header-area{position:fixed;top:0;left:50%;transform:translateX(-50%);width:720px;background:#0a0a0a;z-index:100;padding:.75rem 1rem .5rem 1rem;border-bottom:1px solid #1a1a1a}
.chat-area{flex:1 1 auto;overflow-y:auto;overflow-x:hidden;padding:5.5rem 1rem 6rem 1rem;scrollbar-width:thin;scrollbar-color:#2a2a2a transparent}
.chat-area::-webkit-scrollbar{width:5px}
.chat-area::-webkit-scrollbar-track{background:transparent}
.chat-area::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:3px}
.input-area{position:fixed;bottom:0;left:50%;transform:translateX(-50%);width:720px;background:#0a0a0a;z-index:100;padding:.5rem 1rem .75rem 1rem;border-top:1px solid #1a1a1a}

[data-testid="stChatMessage"]{background:transparent;border:none;padding:.25rem 0;margin:0}
[data-testid="stChatMessageAvatar"]{display:none}
[data-testid="stChatMessageContent"]{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;border-bottom-left-radius:4px;padding:.75rem 1rem;font-size:.9rem;line-height:1.6;color:#e0e0e0}
[data-testid="stChatMessage"] pre{background:#0a0a0a!important;border:1px solid #2a2a2a;border-radius:8px;padding:.75rem;font-size:.8rem;max-width:100%;overflow-x:auto}
[data-testid="stChatMessage"] code{background:#2a2a2a;color:#7dd3fc;padding:1px 5px;border-radius:4px;font-size:.85em}
[data-testid="stChatMessage"] pre code{background:transparent;padding:0;color:inherit}
[data-testid="stChatMessage"] strong{color:#fff;font-weight:600}

[data-testid="stChatInput"] textarea{background:#141414!important;border:1px solid #333!important;border-radius:18px!important;color:#fff!important;font-size:.95rem!important;padding:.875rem 1.125rem!important;min-height:48px!important}
[data-testid="stChatInput"] textarea:focus{border-color:#0a84ff!important}
[data-testid="stChatInput"] textarea::placeholder{color:#555!important}

.stButton>button{background:#0a84ff;color:#fff;border:none;border-radius:12px;padding:.7rem 1.25rem;font-weight:600;font-size:.9rem;width:100%}
.stButton>button:hover{background:#409cff}
.stButton>button[key="reset_top"]{background:transparent;color:#666;border:1px solid #2a2a2a;border-radius:8px;padding:.375rem .75rem;font-size:.75rem;width:auto}
.stButton>button[key="reset_top"]:hover{color:#ff453a;border-color:#ff453a}

.stTextArea textarea{background:#0a0a0a!important;border:1px solid #1a1a1a!important;border-radius:12px!important;font-family:monospace!important;color:#e0e0e0!important;font-size:.875rem!important;padding:.875rem!important;min-height:140px!important}

.card{background:#141414;border:1px solid #2a2a2a;border-radius:16px;padding:1.25rem;margin:.5rem 0;text-align:center}
.card h3{color:#fff;font-size:1.05rem;font-weight:700;margin:0 0 .25rem 0}
.card p{color:#777;font-size:.8rem;margin:0}

.stTextInput input{background:#141414!important;border:1px solid #2a2a2a!important;border-radius:10px!important;color:#fff!important;padding:.5rem .75rem!important}
[data-testid="stInfo"]{background:#0d0d0d;border:1px solid #0a84ff;border-radius:10px;color:#a0c4ff}
[data-testid="stSpinner"]>div{border-top-color:#0a84ff!important}
.label{font-size:.65rem;font-weight:700;color:#0a84ff;text-transform:uppercase;letter-spacing:.08em;margin:.75rem 0 .375rem 0}

.auto-viz{background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:.5rem;margin:.75rem 0}
.auto-viz-label{font-size:.65rem;font-weight:700;color:#0a84ff;text-transform:uppercase;letter-spacing:.08em;padding:.25rem .5rem 0 .5rem}
</style>
""", unsafe_allow_html=True)

# ============ HEADER ============
h1_col, h2_col = st.columns([4, 1])
with h1_col:
    st.markdown('<h1 style="font-size:1.5rem;font-weight:800;letter-spacing:-.04em;margin:0;color:#fff;">Studio.</h1>', unsafe_allow_html=True)
with h2_col:
    if st.button("Reset", key="reset_top"):
        st.session_state.msgs = []
        st.session_state.editor = False
        st.session_state.task = ""
        st.session_state.ran = False
        st.session_state.out = ""
        st.session_state.err = ""
        st.session_state.plot = None
        st.session_state.tested = False
        st.session_state.model = None
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()

if st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:.65rem;text-align:center;margin:.25rem 0 0 0;">' + st.session_state.model + '</p>', unsafe_allow_html=True)
elif KEY:
    st.markdown('<p style="color:#ffd60a;font-size:.65rem;text-align:center;margin:.25rem 0 0 0;">Set model to begin</p>', unsafe_allow_html=True)
else:
    st.markdown('<p style="color:#ff453a;font-size:.65rem;text-align:center;margin:.25rem 0 0 0;">No API key</p>', unsafe_allow_html=True)

# ============ MODEL SETUP ============
if not st.session_state.tested:
    mc1, mc2 = st.columns([3, 1])
    with mc1:
        manual = st.text_input("Model", value="step-5-preview", key="manual_model")
    with mc2:
        st.write("")
        if st.button("Set"):
            st.session_state.model = manual
            st.session_state.tested = True
            st.rerun()
    if st.button("Auto-Test"):
        with st.spinner("Testing..."):
            model, status = test_api()
        if model:
            st.session_state.tested = True
            st.rerun()

# ============ START ============
if len(st.session_state.msgs) == 0 and st.session_state.tested:
    st.markdown('<div class="card"><h3>Topology Optimization</h3><p>Build a structural solver</p></div>', unsafe_allow_html=True)
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

# ============ CHAT DISPLAY ============
for msg_idx, m in enumerate(st.session_state.msgs):
    role = m.get("role", "user")
    content = m.get("content", "")

    if role == "user":
        text = clean(content)
        if text:
            _, c = st.columns([0.3, 0.7])
            with c:
                with st.chat_message("user"):
                    st.write(text)
    else:
        text = clean(content)

        # Find ALL matplotlib code in the message
        code_blocks = find_matplotlib_code(content)

        # Remove code from text display to avoid duplication
        for cb in code_blocks:
            if cb in text:
                text = text.replace(cb, "")
            # Also remove markdown version
            text = text.replace("```python\n" + cb + "\n```", "")
            text = text.replace("```" + cb + "```", "")

        text = text.strip()
        text = re.sub(r"```\w*\n?.*?```", "", text, flags=re.DOTALL).strip()

        if text:
            c, _ = st.columns([0.78, 0.22])
            with c:
                with st.chat_message("assistant"):
                    st.write(text)

        # Execute and show each code block
        for i, code in enumerate(code_blocks):
            unique_key = f"viz_{msg_idx}_{i}"

            st.markdown('<div class="auto-viz"><div class="auto-viz-label">Visualization</div>', unsafe_allow_html=True)
            execute_and_show(code, unique_key)
            st.markdown('</div>', unsafe_allow_html=True)

# ============ PRACTICE ============
if st.session_state.editor:
    st.markdown('<div class="label">Practice</div>', unsafe_allow_html=True)
    if st.session_state.task:
        st.info(st.session_state.task)

    code = st.text_area("code", value=st.session_state.code, height=150, key="practice_box", label_visibility="collapsed")

    a, b = st.columns(2)
    with a:
        if st.button("Run Code", type="primary"):
            st.session_state.code = code
            with st.spinner("Running..."):
                out, err, fig = run_code(code)
                st.session_state.out = out or ""
                st.session_state.err = err or ""
                st.session_state.ran = True
                st.session_state.plot = fig

    with b:
        if st.button("Submit to Mentor"):
            if not st.session_state.ran:
                st.warning("Run first")
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
            st.markdown('<div style="background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:10px;padding:.75rem;font-family:monospace;font-size:.8rem;color:#30d158;white-space:pre-wrap;margin:.5rem 0;">' + st.session_state.out + '</div>', unsafe_allow_html=True)
        if st.session_state.err and "Traceback" in st.session_state.err:
            lines = st.session_state.err.split("\n")
            st.markdown('<div style="background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:10px;padding:.75rem;font-family:monospace;font-size:.8rem;color:#ff453a;white-space:pre-wrap;margin:.5rem 0;">' + "\n".join(lines[-4:]) + '</div>', unsafe_allow_html=True)
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
                st.write(clean(reply))

        st.session_state.msgs.append({"role": "assistant", "content": reply})
        save()
        st.rerun()
