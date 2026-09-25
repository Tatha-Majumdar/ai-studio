import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import re
import json

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
    "You are a senior engineering mentor teaching Topology Optimization and System Design. "
    "The student may have zero coding experience. "
    "RULES: Ask one question then stop and wait. Never say imagine or visualize. "
    "Always show concepts with matplotlib code the student can run. "
    "End practice exercises with [PRACTICE] then the task description. "
    "Keep responses under 150 words. One concept at a time. "
    "Start by asking about their coding experience."
)

def test_api():
    if not KEY:
        return None, "No API key in Secrets"
    models = ["step-5-preview", "step-5", "step-3", "step-2", "step-1-8k", "step-1-32k"]
    results = []
    for m in models:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=10)
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say OK"}], max_tokens=5)
            if r.choices[0].message.content:
                results.append("OK: " + m)
                if not st.session_state.model:
                    st.session_state.model = m
                    return m, "Connected using " + m
        except Exception as e:
            err = str(e)
            if "401" in err:
                return None, "Invalid API key"
            results.append("FAIL: " + m)
    return None, "No model works. Tried: " + ", ".join(results)

def ask_ai(msg):
    if not KEY:
        return "No API key found. Go to Settings > Secrets > add STEPFUN_API_KEY"
    if not st.session_state.model:
        model, status = test_api()
        if not model:
            return "ERROR: " + status
    try:
        c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=30)
        chat = [{"role": "system", "content": PROMPT}]
        for x in st.session_state.msgs:
            chat.append({"role": x.get("role", "user"), "content": x.get("content", "")})
        chat.append({"role": "user", "content": msg})
        r = c.chat.completions.create(model=st.session_state.model, messages=chat, max_tokens=3000, temperature=0.6)
        reply = r.choices[0].message.content
        if reply:
            if "[PRACTICE]" in reply:
                match = re.search(r"\[PRACTICE\]\s*(.+)", reply, re.DOTALL)
                if match:
                    st.session_state.task = match.group(1).strip()
                    st.session_state.editor = True
                    st.session_state.ran = False
                    st.session_state.out = ""
                    st.session_state.err = ""
            return reply
        return "Empty response. Try again."
    except Exception as e:
        err = str(e)
        if "404" in err:
            st.session_state.model = None
            return "Model not found. Click Test to find a working model."
        if "401" in err:
            return "Invalid API key"
        if "429" in err:
            return "Rate limited. Wait 30 seconds."
        return "Error: " + err[:100]

def run_code(code):
    if not code:
        return "", "No code", None
    old_out, old_err = sys.stdout, sys.stderr
    cap_out, cap_err = io.StringIO(), io.StringIO()
    ns = {"__name__": "__main__"}
    try:
        import numpy as np
        ns["np"] = np
    except:
        pass
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

st.set_page_config(page_title="Studio", layout="centered")

st.markdown("""
<style>
.stApp {background:#0a0a0a;color:#fff;font-family:-apple-system,sans-serif}
#MainMenu,footer,header{visibility:hidden}
[data-testid="stSidebar"]{display:none}
.block-container{max-width:700px;padding-top:1rem;padding-bottom:5rem}
.title{text-align:center;font-size:2rem;font-weight:800;color:#fff;letter-spacing:-.04em;padding:.5rem 0}
.sub{text-align:center;font-size:.85rem;color:#666;margin-bottom:1rem}
[data-testid="stChatMessage"]{background:transparent;border:none;padding:.25rem 0}
[data-testid="stChatMessageAvatar"]{display:none}
[data-testid="stChatMessageContent"]{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;border-bottom-left-radius:4px;padding:.8rem 1rem;font-size:.95rem;line-height:1.6;color:#e0e0e0}
[data-testid="stChatMessage"] pre{background:#0a0a0a;border:1px solid #2a2a2a;border-radius:8px;padding:.8rem;font-size:.8rem}
[data-testid="stChatMessage"] code{background:#2a2a2a;color:#7dd3fc;padding:2px 5px;border-radius:4px;font-size:.85em}
[data-testid="stChatInput"] textarea{background:#141414!important;border:1px solid #333!important;border-radius:20px!important;color:#fff!important;font-size:1rem!important;padding:1rem 1.25rem!important;min-height:56px!important}
[data-testid="stChatInput"] textarea:focus{border-color:#0a84ff!important}
.stButton>button{background:#0a84ff;color:#fff;border:none;border-radius:12px;padding:.75rem 1.5rem;font-weight:600;font-size:.95rem;width:100%}
.stButton>button:hover{background:#409cff}
.stTextArea textarea{background:#0a0a0a!important;border:1px solid #1a1a1a!important;border-radius:12px!important;font-family:monospace!important;color:#e0e0e0!important;font-size:.9rem!important;padding:1rem!important;min-height:160px!important}
.card{background:#141414;border:1px solid #2a2a2a;border-radius:16px;padding:1.25rem;margin:.5rem 0;text-align:center}
.card h3{color:#fff;font-size:1.1rem;font-weight:700;margin:0 0 .25rem 0}
.card p{color:#777;font-size:.8rem;margin:0}
.good{background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:10px;padding:.8rem;font-family:monospace;font-size:.85rem;color:#30d158;white-space:pre-wrap;margin:.5rem 0}
.bad{background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:10px;padding:.8rem;font-family:monospace;font-size:.85rem;color:#ff453a;white-space:pre-wrap;margin:.5rem 0}
.label{font-size:.7rem;font-weight:700;color:#0a84ff;text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .5rem 0}
hr{border:none;height:1px;background:#1a1a1a;margin:1rem 0}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">Studio.</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Learn Engineering. Build Real Things.</div>', unsafe_allow_html=True)

if not st.session_state.tested:
    c1, c2 = st.columns([3, 1])
    with c1:
        manual = st.text_input("Model name", value="step-5-preview", key="manual_model")
    with c2:
        if st.button("Set Model"):
            st.session_state.model = manual
            st.session_state.tested = True
            st.success("Set: " + manual)
    if st.button("Auto-Test Connection"):
        with st.spinner("Testing..."):
            model, status = test_api()
        if model:
            st.session_state.tested = True
            st.success(status)
        else:
            st.error(status)
elif st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:.75rem;text-align:center;margin:0 0 1rem 0;">Connected: ' + st.session_state.model + '</p>', unsafe_allow_html=True)

if len(st.session_state.msgs) == 0:
    st.write("")
    st.markdown('<div class="card"><h3>Topology Optimization</h3><p>Build a structural solver from scratch</p></div>', unsafe_allow_html=True)
    if st.button("Start Topology Optimization", type="primary"):
        st.session_state.start = "topo"
    st.markdown('<div class="card"><h3>System Design</h3><p>Design and build real systems</p></div>', unsafe_allow_html=True)
    if st.button("Start System Design", type="primary"):
        st.session_state.start = "sys"

if st.session_state.start:
    track = st.session_state.start
    st.session_state.start = None
    msg = "I want to learn " + ("Topology Optimization" if track == "topo" else "System Design") + " from the very beginning."
    st.session_state.msgs = [{"role": "user", "content": msg}]
    with st.spinner("Starting..."):
        reply = ask_ai(msg)
    st.session_state.msgs.append({"role": "assistant", "content": reply})
    save()
    st.rerun()

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

if st.session_state.editor:
    st.markdown('<div class="label">Practice</div>', unsafe_allow_html=True)
    if st.session_state.task:
        st.info(st.session_state.task)
    code = st.text_area("code", value=st.session_state.code, height=180, key="editor_box", label_visibility="collapsed")
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
            st.markdown('<div class="good">' + st.session_state.out + '</div>', unsafe_allow_html=True)
        if st.session_state.err and "Traceback" in st.session_state.err:
            lines = st.session_state.err.split("\n")
            st.markdown('<div class="bad">' + "\n".join(lines[-4:]) + '</div>', unsafe_allow_html=True)
    if st.session_state.plot is not None:
        st.markdown('<div class="label">Plot</div>', unsafe_allow_html=True)
        try:
            st.pyplot(st.session_state.plot, use_container_width=True)
        except:
            pass

if len(st.session_state.msgs) > 0:
    if msg := st.chat_input("Type your answer..."):
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
        st.session_state.tested = False
        st.session_state.model = None
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()
