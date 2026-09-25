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

API_BASE = "https://api.stepfun.ai/step_plan/v1"
HISTORY = "data.json"

if "msgs" not in st.session_state:
    st.session_state.msgs = []
if "visual_log" not in st.session_state:
    st.session_state.visual_log = []
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
if "plot_desc" not in st.session_state:
    st.session_state.plot_desc = ""
if "start" not in st.session_state:
    st.session_state.start = None
if "model" not in st.session_state:
    st.session_state.model = None
if "tested" not in st.session_state:
    st.session_state.tested = False

def save():
    try:
        d = {"msgs": st.session_state.msgs, "model": st.session_state.model, "visual_log": st.session_state.visual_log}
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
            if "visual_log" in d:
                st.session_state.visual_log = d["visual_log"]
    except:
        pass

load()

KEY = ""
try:
    KEY = st.secrets["STEPFUN_API_KEY"]
except:
    KEY = os.environ.get("STEPFUN_API_KEY", "")

PROMPT = (
    "You are an engineering mentor teaching Topology Optimization and System Design to a beginner. "
    "RULES: Show every concept with matplotlib code first, then explain what they see. "
    "Never say imagine or visualize. Keep text under 100 words. "
    "Ask one question then stop. Use [PRACTICE] for coding exercises. "
    "Start by asking about their coding experience."
)

def test_api():
    if not KEY:
        return None, "No API key in Secrets"
    models = ["step-5-preview", "step-5", "step-3", "step-2", "step-1-8k", "step-1-32k"]
    for m in models:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=10)
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say OK"}], max_tokens=10)
            content = r.choices[0].message.content
            if content and len(content.strip()) > 0:
                if not st.session_state.model:
                    st.session_state.model = m
                return m, "Connected: " + m
        except Exception as e:
            err = str(e)
            if "401" in err:
                return None, "Invalid API key"
    return None, "No model works"

def ask_ai(msg, retry=True):
    if not KEY:
        return "No API key found"
    if not st.session_state.model:
        model, status = test_api()
        if not model:
            return "ERROR: " + status

    try:
        c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=60)

        chat = []
        chat.append({"role": "system", "content": PROMPT})

        for x in st.session_state.msgs[-10:]:
            role = x.get("role", "user")
            content = x.get("content", "")
            if content and len(content) > 0:
                if len(content) > 2000:
                    content = content[:2000]
                chat.append({"role": role, "content": content})

        chat.append({"role": "user", "content": msg[:2000]})

        r = c.chat.completions.create(
            model=st.session_state.model,
            messages=chat,
            max_tokens=2000,
            temperature=0.7,
        )

        if r.choices:
            choice = r.choices[0]
            content = choice.message.content
            finish = choice.finish_reason

            if content and len(content.strip()) > 2:
                reply = content.strip()
                if "[PRACTICE]" in reply:
                    match = re.search(r"\[PRACTICE\]\s*(.+)", reply, re.DOTALL)
                    if match:
                        st.session_state.task = match.group(1).strip()
                        st.session_state.editor = True
                        st.session_state.ran = False
                        st.session_state.out = ""
                        st.session_state.err = ""
                return reply

            if finish == "length":
                if retry:
                    return ask_ai(msg, retry=False)
                return "Response was cut off. Try a shorter question."

            if content is None and finish == "content_filter":
                return "The model filtered the response. Try rephrasing."

        if retry:
            time.sleep(1)
            return ask_ai(msg, retry=False)

        return "The AI returned an empty response. Try sending your message again."

    except Exception as e:
        err = str(e)
        if "404" in err:
            st.session_state.model = None
            st.session_state.tested = False
            return "Model not found. Click Auto-Test."
        if "429" in err:
            return "Rate limited. Wait 30 seconds and try again."
        if "timeout" in err.lower():
            return "Connection timed out. Try again."
        return "Error: " + err[:80]

import time

def run_code(code):
    if not code:
        return "", "No code", None, ""
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
        fig, desc = None, ""
        try:
            nums = plt.get_fignums()
            if nums:
                fig = plt.figure(nums[0])
                desc = describe_figure(fig)
                plt.close("all")
        except:
            pass
        return out, err, fig, desc
    except:
        sys.stdout, sys.stderr = old_out, old_err
        return cap_out.getvalue(), traceback.format_exc(), None, ""

def describe_figure(fig):
    if fig is None:
        return "No plot"
    parts = []
    try:
        for ax in fig.axes:
            if ax.get_title():
                parts.append(ax.get_title())
            lines = ax.get_lines()
            if lines:
                parts.append(str(len(lines)) + " lines")
            images = ax.get_images()
            if images:
                for img in images:
                    try:
                        data = np.asarray(img.get_array())
                        parts.append("grid " + str(data.shape[0]) + "x" + str(data.shape[1]))
                    except:
                        pass
            if ax.patches:
                parts.append(str(len(ax.patches)) + " shapes")
        return ", ".join(parts) if parts else "plot"
    except:
        return "plot"

def verify_plot(fig):
    if fig is None:
        return False, "No figure"
    if not fig.axes:
        return False, "No axes"
    for ax in fig.axes:
        if ax.get_lines() or ax.get_images() or ax.patches:
            return True, "OK"
    return False, "Empty"

def clean(t):
    if not t:
        return ""
    return re.sub(r"\[PRACTICE\].*", "", t, flags=re.DOTALL).strip()

def extract_code_blocks(text):
    return [m.strip() for m in re.findall(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)]

def has_matplotlib(code):
    return "plt." in code or "matplotlib" in code

st.set_page_config(page_title="Studio", layout="centered")

st.markdown("""
<style>
html,body,.stApp{background:#0a0a0a;color:#fff;font-family:-apple-system,sans-serif;height:100vh;overflow:hidden}
#MainMenu,footer,header,[data-testid="stSidebar"],[data-testid="stToolbar"]{display:none!important}
.block-container{max-width:720px;height:calc(100vh - 1rem);display:flex;flex-direction:column;overflow:hidden;padding-top:0.5rem;padding-bottom:0;margin:0 auto}
[data-testid="stChatMessage"]{background:transparent;border:none;padding:0.25rem 0;margin:0}
[data-testid="stChatMessageAvatar"]{display:none}
[data-testid="stChatMessageContent"]{background:#1a1a1a;border:1px solid #2a2a2a;border-radius:16px;border-bottom-left-radius:4px;padding:0.75rem 1rem;font-size:0.9rem;line-height:1.6;color:#e0e0e0}
[data-testid="stChatMessage"] pre{background:#0a0a0a!important;border:1px solid #2a2a2a;border-radius:8px;padding:0.75rem;font-size:0.8rem;max-width:100%;overflow-x:auto}
[data-testid="stChatMessage"] code{background:#2a2a2a;color:#7dd3fc;padding:1px 5px;border-radius:4px;font-size:0.85em}
[data-testid="stChatMessage"] pre code{background:transparent;padding:0;color:inherit}
[data-testid="stChatMessage"] strong{color:#fff;font-weight:600}
[data-testid="stChatInput"]{flex-shrink:0;padding:0.5rem 0 0.25rem 0;border-top:1px solid #1a1a1a;background:#0a0a0a}
[data-testid="stChatInput"] textarea{background:#141414!important;border:1px solid #333!important;border-radius:18px!important;color:#fff!important;font-size:0.95rem!important;padding:0.875rem 1.125rem!important;min-height:48px!important}
[data-testid="stChatInput"] textarea:focus{border-color:#0a84ff!important}
.stButton>button{background:#0a84ff;color:#fff;border:none;border-radius:12px;padding:0.7rem 1.25rem;font-weight:600;font-size:0.9rem;width:100%}
.stButton>button:hover{background:#409cff}
.stButton>button[key="reset_top"]{background:transparent;color:#666;border:1px solid #2a2a2a;border-radius:8px;padding:0.375rem 0.75rem;font-size:0.75rem;width:auto}
.stButton>button[key="reset_top"]:hover{color:#ff453a;border-color:#ff453a}
.stTextArea textarea{background:#0a0a0a!important;border:1px solid #1a1a1a!important;border-radius:12px!important;font-family:monospace!important;color:#e0e0e0!important;font-size:0.875rem!important;padding:0.875rem!important;min-height:140px!important}
.card{background:#141414;border:1px solid #2a2a2a;border-radius:16px;padding:1.25rem;margin:0.5rem 0;text-align:center}
.card h3{color:#fff;font-size:1.05rem;font-weight:700;margin:0 0 0.25rem 0}
.card p{color:#777;font-size:0.8rem;margin:0}
.good{background:#0d0d0d;border:1px solid rgba(48,209,88,.3);border-radius:10px;padding:0.75rem;font-family:monospace;font-size:0.8rem;color:#30d158;white-space:pre-wrap;margin:0.5rem 0}
.bad{background:#1a0d0d;border:1px solid rgba(255,69,58,.3);border-radius:10px;padding:0.75rem;font-family:monospace;font-size:0.8rem;color:#ff453a;white-space:pre-wrap;margin:0.5rem 0}
.plot-box{background:#141414;border:1px solid #2a2a2a;border-radius:12px;padding:0.5rem;margin:0.75rem 0}
.plot-label{font-size:0.65rem;font-weight:700;color:#0a84ff;text-transform:uppercase;letter-spacing:0.08em;padding:0.25rem 0.5rem 0 0.5rem}
.ai-sees{background:#0d1520;border:1px solid rgba(10,132,255,.2);border-radius:8px;padding:0.4rem 0.6rem;margin:0.25rem 0 0.5rem 0.5rem;font-size:0.7rem;color:#7dd3fc;font-style:italic}
.label{font-size:0.65rem;font-weight:700;color:#0a84ff;text-transform:uppercase;letter-spacing:0.08em;margin:0.75rem 0 0.375rem 0}
.stTextInput input{background:#141414!important;border:1px solid #2a2a2a!important;border-radius:10px!important;color:#fff!important;padding:0.5rem 0.75rem!important}
[data-testid="stInfo"]{background:#0d0d0d;border:1px solid #0a84ff;border-radius:10px;color:#a0c4ff}
[data-testid="stSpinner"]>div{border-top-color:#0a84ff!important}
</style>
""", unsafe_allow_html=True)

tb_left, tb_right = st.columns([4, 1])
with tb_left:
    st.markdown('<h1 style="font-size:1.5rem;font-weight:800;letter-spacing:-.04em;margin:0;">Studio.</h1>', unsafe_allow_html=True)
with tb_right:
    if st.button("Reset", key="reset_top"):
        st.session_state.msgs = []
        st.session_state.editor = False
        st.session_state.task = ""
        st.session_state.ran = False
        st.session_state.out = ""
        st.session_state.err = ""
        st.session_state.plot = None
        st.session_state.plot_desc = ""
        st.session_state.visual_log = []
        st.session_state.tested = False
        st.session_state.model = None
        try:
            os.remove(HISTORY)
        except:
            pass
        st.rerun()

if st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:0.7rem;text-align:center;margin:0.25rem 0;">Connected: ' + st.session_state.model + '</p>', unsafe_allow_html=True)
elif KEY:
    st.markdown('<p style="color:#ffd60a;font-size:0.7rem;text-align:center;margin:0.25rem 0;">Set a model to begin</p>', unsafe_allow_html=True)
else:
    st.markdown('<p style="color:#ff453a;font-size:0.7rem;text-align:center;margin:0.25rem 0;">No API key in Secrets</p>', unsafe_allow_html=True)

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
    msg = "I want to learn " + ("Topology Optimization" if track == "topo" else "System Design") + " from the very beginning."
    st.session_state.msgs = [{"role": "user", "content": msg}]

    with st.spinner("Starting..."):
        reply = ask_ai(msg)

        if "empty response" in reply.lower() or "error" in reply.lower():
            time.sleep(2)
            reply = ask_ai(msg)

    st.session_state.msgs.append({"role": "assistant", "content": reply})
    save()
    st.rerun()

for m in st.session_state.msgs:
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
        if text:
            c, _ = st.columns([0.78, 0.22])
            with c:
                with st.chat_message("assistant"):
                    st.write(text)

        code_blocks = extract_code_blocks(content)
        for block in code_blocks:
            if has_matplotlib(block):
                out, err, fig, desc = run_code(block)
                if fig is not None:
                    ok, status = verify_plot(fig)
                    if ok:
                        st.markdown('<div class="plot-box"><div class="plot-label">Visualization</div>', unsafe_allow_html=True)
                        try:
                            st.pyplot(fig, use_container_width=True)
                        except:
                            st.caption("Render error")
                        st.markdown('</div>', unsafe_allow_html=True)
                        if desc:
                            st.markdown('<div class="ai-sees">AI sees: ' + desc + '</div>', unsafe_allow_html=True)
                            st.session_state.visual_log.append(desc)

if st.session_state.editor:
    st.markdown('<div class="label">Practice</div>', unsafe_allow_html=True)
    if st.session_state.task:
        st.info(st.session_state.task)

    code = st.text_area("code", value=st.session_state.code, height=150, key="editor_box", label_visibility="collapsed")

    a, b = st.columns(2)
    with a:
        if st.button("Run Code", type="primary"):
            st.session_state.code = code
            with st.spinner("Running..."):
                out, err, fig, desc = run_code(code)
                st.session_state.out = out or ""
                st.session_state.err = err or ""
                st.session_state.ran = True
                st.session_state.plot = fig
                st.session_state.plot_desc = desc

    with b:
        if st.button("Submit to Mentor"):
            if not st.session_state.ran:
                st.warning("Run first")
            else:
                sub = "I did the exercise.\n\nMy code:\n```python\n" + code + "\n```\n"
                if st.session_state.out:
                    sub += "Output:\n```\n" + st.session_state.out + "\n```\n"
                if st.session_state.plot_desc:
                    sub += "My plot: " + st.session_state.plot_desc + "\n"
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
        st.markdown('<div class="plot-box"><div class="plot-label">Your Plot</div>', unsafe_allow_html=True)
        try:
            st.pyplot(st.session_state.plot, use_container_width=True)
        except:
            pass
        st.markdown('</div>', unsafe_allow_html=True)
        if st.session_state.plot_desc:
            st.markdown('<div class="ai-sees">AI sees: ' + st.session_state.plot_desc + '</div>', unsafe_allow_html=True)

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

        code_blocks = extract_code_blocks(reply)
        for block in code_blocks:
            if has_matplotlib(block):
                out, err, fig, desc = run_code(block)
                if fig is not None:
                    ok, status = verify_plot(fig)
                    if ok:
                        st.markdown('<div class="plot-box"><div class="plot-label">Visualization</div>', unsafe_allow_html=True)
                        try:
                            st.pyplot(fig, use_container_width=True)
                        except:
                            pass
                        st.markdown('</div>', unsafe_allow_html=True)
                        if desc:
                            st.markdown('<div class="ai-sees">AI sees: ' + desc + '</div>', unsafe_allow_html=True)
                            st.session_state.visual_log.append(desc)

        st.session_state.msgs.append({"role": "assistant", "content": reply})
        save()
