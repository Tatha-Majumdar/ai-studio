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

# ============ SESSION STATE ============
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
if "start" not in st.session_state:
    st.session_state.start = None
if "model" not in st.session_state:
    st.session_state.model = None
if "tested" not in st.session_state:
    st.session_state.tested = False
if "debug" not in st.session_state:
    st.session_state.debug = []

# ============ PERSISTENCE ============
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

# ============ API KEY ============
KEY = ""
try:
    KEY = st.secrets["STEPFUN_API_KEY"]
except:
    KEY = os.environ.get("STEPFUN_API_KEY", "")

# ============ PAGE CONFIG ============
st.set_page_config(page_title="Studio", layout="centered")

# ============ CSS ============
st.markdown("""
<style>
html,body{
    margin:0;padding:0;background:#0a0a0a;color:#fff;
    font-family:-apple-system,BlinkMacSystemFont,sans-serif;
    overflow-x:hidden;overflow-y:auto;scroll-behavior:smooth;
}
.stApp{min-height:100vh;background:#0a0a0a}
#MainMenu,footer,header,[data-testid="stSidebar"],[data-testid="stToolbar"]{display:none!important}

.header-fix{position:fixed;top:0;left:50%;transform:translateX(-50%);width:720px;max-width:95vw;background:#0a0a0a;z-index:100;padding:.6rem .75rem .4rem .75rem;border-bottom:1px solid #1a1a1a}

.block-container{max-width:720px;margin:0 auto;padding-top:4.5rem;padding-bottom:2rem;padding-left:.75rem;padding-right:.75rem}

[data-testid="stChatInput"]{position:sticky;bottom:0;background:#0a0a0a;z-index:50;padding:.5rem 0 .75rem 0}
[data-testid="stChatInput"] textarea{background:#141414!important;border:1px solid #333!important;border-radius:18px!important;color:#fff!important;font-size:.95rem!important;padding:.875rem 1.125rem!important;min-height:48px!important;box-shadow:0 2px 8px rgba(0,0,0,.4)!important}
[data-testid="stChatInput"] textarea:focus{border-color:#0a84ff!important}
[data-testid="stChatInput"] textarea::placeholder{color:#555!important}

[data-testid="stChatMessage"]{background:transparent;border:none;padding:.25rem 0;margin:0}
[data-testid="stChatMessageAvatar"]{display:none}
[data-testid="stChatMessageContent"]{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;border-bottom-left-radius:4px;padding:.75rem 1rem;font-size:.9rem;line-height:1.6;color:#e0e0e0}
[data-testid="stChatMessage"] pre{background:#0a0a0a!important;border:1px solid #2a2a2a;border-radius:8px;padding:.75rem;font-size:.8rem;max-width:100%;overflow-x:auto}
[data-testid="stChatMessage"] code{background:#2a2a2a;color:#7dd3fc;padding:1px 5px;border-radius:4px;font-size:.85em}
[data-testid="stChatMessage"] pre code{background:transparent;padding:0;color:inherit}
[data-testid="stChatMessage"] strong{color:#fff;font-weight:600}

.stButton>button{background:#0a84ff;color:#fff;border:none;border-radius:10px;padding:.6rem 1.2rem;font-weight:600;font-size:.875rem;width:100%;transition:background .15s}
.stButton>button:hover{background:#409cff}
.stButton>button[key="reset_top"]{background:transparent;color:#666;border:1px solid #2a2a2a;border-radius:8px;padding:.375rem .6rem;font-size:.7rem;width:auto}
.stButton>button[key="reset_top"]:hover{color:#ff453a;border-color:#ff453a}
.stButton>button[key="debug_btn"]{background:transparent;color:#888;border:1px solid #2a2a2a;border-radius:8px;padding:.375rem .6rem;font-size:.7rem;width:auto}

.stTextArea textarea{background:#0a0a0a!important;border:1px solid #2a2a2a!important;border-radius:12px!important;font-family:monospace!important;color:#e0e0e0!important;font-size:.875rem!important;padding:.875rem!important;min-height:130px!important}
.stTextArea textarea:focus{border-color:#0a84ff!important}

.card{background:#141414;border:1px solid #2a2a2a;border-radius:16px;padding:1.25rem;margin:.5rem 0;text-align:center}
.card h3{color:#fff;font-size:1.05rem;font-weight:700;margin:0 0 .25rem 0}
.card p{color:#777;font-size:.8rem;margin:0}

.stTextInput input{background:#141414!important;border:1px solid #2a2a2a!important;border-radius:10px!important;color:#fff!important;padding:.5rem .75rem!important}
.stTextInput input:focus{border-color:#0a84ff!important}

[data-testid="stInfo"]{background:#0d0d0d;border:1px solid #0a84ff;border-radius:10px;color:#a0c4ff}
[data-testid="stSpinner"]>div{border-top-color:#0a84ff!important}

.chat-output{background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:8px;padding:.6rem;font-family:monospace;font-size:.8rem;color:#30d158;white-space:pre-wrap;margin:.5rem 0}
.chat-error{background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:8px;padding:.6rem;font-family:monospace;font-size:.8rem;color:#ff453a;white-space:pre-wrap;margin:.5rem 0}

::-webkit-scrollbar{width:5px}
::-webkit-scrollbar-track{background:#0a0a0a}
::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#3a3a3a}
</style>
""", unsafe_allow_html=True)

# ============ AUTO SCROLL ============
st.markdown("""
<script>
window.addEventListener('load', function() {
    setTimeout(function() {
        window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    }, 100);
});
</script>
""", unsafe_allow_html=True)

# ============ API FUNCTIONS ============
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
        return "No API key found"
    if not st.session_state.model:
        model, _ = test_api()
        if not model:
            return "No model found. Click Auto-Test."

    instructions = (
        "You are an engineering mentor teaching Topology Optimization. "
        "Student is a beginner. Show matplotlib code in python code blocks. "
        "Never say imagine. Under 100 words. Ask one question then stop. "
        "NumPy and matplotlib are pre-installed. Code runs automatically."
    )

    for attempt in range(3):
        # Try Format 1: system + user
        result = try_call(instructions, msg, use_system=True)
        if result:
            return result

        # Try Format 2: no system, instructions as user
        result = try_call(instructions, msg, use_system=False)
        if result:
            return result

        time.sleep(1)

    return "Could not get response. Click Debug for details."

def try_call(instructions, msg, use_system=True):
    try:
        c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=45)

        if use_system:
            chat = [{"role": "system", "content": instructions}]
        else:
            chat = [{"role": "user", "content": instructions}]

        if not use_system:
            chat.append({"role": "assistant", "content": "Understood."})

        for x in st.session_state.msgs[-6:]:
            content = x.get("content", "")[:500]
            if content:
                chat.append({"role": x.get("role", "user"), "content": content})

        chat.append({"role": "user", "content": msg[:1000]})

        r = c.chat.completions.create(model=st.session_state.model, messages=chat, max_tokens=1500, temperature=0.7)

        if r.choices and r.choices[0].message.content:
            reply = r.choices[0].message.content.strip()
            if len(reply) > 3:
                if use_system:
                    st.session_state.debug.append("system format worked")
                else:
                    st.session_state.debug.append("user format worked")
                if "[PRACTICE]" in reply:
                    match = re.search(r"\[PRACTICE\]\s*(.+)", reply, re.DOTALL)
                    if match:
                        st.session_state.task = match.group(1).strip()
                        st.session_state.editor = True
                        st.session_state.ran = False
                return reply
            else:
                st.session_state.debug.append(f"format {'system' if use_system else 'user'}: too short")
        else:
            st.session_state.debug.append(f"format {'system' if use_system else 'user'}: empty/None")
    except Exception as e:
        st.session_state.debug.append(f"format {'system' if use_system else 'user'} error: {str(e)[:40]}")
    return None

# ============ CODE EXECUTION ============
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
    t = re.sub(r"\[PRACTICE\].*", "", t, flags=re.DOTALL)
    return t.strip()

def find_code(text):
    if not text:
        return []
    blocks = []
    pattern = r"```python\s*\n(.*?)```"
    matches = re.findall(pattern, text, flags=re.DOTALL)
    for m in matches:
        if "plt." in m or "matplotlib" in m:
            blocks.append(m.strip())
    if not blocks:
        pattern2 = r"```\s*\n(.*?)```"
        matches2 = re.findall(pattern2, text, flags=re.DOTALL)
        for m in matches2:
            if "plt." in m or "import" in m:
                blocks.append(m.strip())
    return blocks

def remove_code(text, blocks):
    for cb in blocks:
        text = text.replace("```python\n" + cb + "\n```", "")
        text = text.replace("```" + cb + "```", "")
    text = re.sub(r"```python\s*\n.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"```\s*\n.*?```", "", text, flags=re.DOTALL)
    return text.strip()

# ============ HEADER (Fixed) ============
st.markdown('<div class="header-fix">', unsafe_allow_html=True)

h1, h2, h3 = st.columns([3, 1, 1])
with h1:
    st.markdown('<h1 style="font-size:1.4rem;font-weight:800;letter-spacing:-.04em;margin:0;color:#fff;">Studio.</h1>', unsafe_allow_html=True)
with h2:
    if st.button("Debug", key="debug_btn"):
        if st.session_state.debug:
            for d in st.session_state.debug[-5:]:
                st.text(d)
        else:
            st.text("No debug info yet")
with h3:
    if st.button("Reset", key="reset_top"):
        st.session_state.msgs = []
        st.session_state.editor = False
        st.session_state.task = ""
        st.session_state.ran = False
        st.session_state.out = ""
        st.session_state.err = ""
        st.session_state.tested = False
        st.session_state.model = None
        st.session_state.debug = []
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()

if st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:.6rem;text-align:center;margin:.1rem 0 0 0;">' + st.session_state.model + '</p>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

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
        else:
            st.error(status)

# ============ START SCREEN ============
if len(st.session_state.msgs) == 0 and st.session_state.tested:
    st.markdown('<div class="card"><h3>Topology Optimization</h3><p>Build a structural solver from scratch</p></div>', unsafe_allow_html=True)
    if st.button("Start Topology Optimization", type="primary"):
        st.session_state.start = "topo"
    st.markdown('<div class="card"><h3>System Design</h3><p>Design and build real systems</p></div>', unsafe_allow_html=True)
    if st.button("Start System Design", type="primary"):
        st.session_state.start = "sys"

# ============ HANDLE START ============
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
        code_blocks = find_code(content)
        text = clean(content)
        text = remove_code(text, code_blocks)

        c, _ = st.columns([0.78, 0.22])
        with c:
            # Show text
            if text:
                with st.chat_message("assistant"):
                    st.write(text)

            # Execute and show plots inline
            for code in code_blocks:
                with st.chat_message("assistant"):
                    out, err, fig = run_code(code)
                    if fig is not None:
                        st.pyplot(fig, use_container_width=True)
                    if out:
                        st.markdown('<div class="chat-output">' + out + '</div>', unsafe_allow_html=True)
                    if err and "Traceback" in err:
                        lines = err.split("\n")
                        st.markdown('<div class="chat-error">' + "\n".join(lines[-3:]) + '</div>', unsafe_allow_html=True)

            # Practice sandbox inline
            if st.session_state.editor and msg_idx == len(st.session_state.msgs) - 1:
                if st.session_state.task:
                    st.info("Practice: " + st.session_state.task)

                code = st.text_area("code", value=st.session_state.code, height=140, key=f"p{msg_idx}", label_visibility="collapsed")

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
                        st.markdown('<div class="chat-output">' + st.session_state.out + '</div>', unsafe_allow_html=True)
                    if st.session_state.err and "Traceback" in st.session_state.err:
                        lines = st.session_state.err.split("\n")
                        st.markdown('<div class="chat-error">' + "\n".join(lines[-3:]) + '</div>', unsafe_allow_html=True)
                    if st.session_state.plot is not None:
                        st.pyplot(st.session_state.plot, use_container_width=True)

# ============ CHAT INPUT ============
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
                code_blocks = find_code(reply)
                text = clean(reply)
                text = remove_code(text, code_blocks)
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
