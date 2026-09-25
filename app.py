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
    "You are a teaching harness for engineering education. You teach Topology Optimization and System Design. "
    "The student is a complete beginner.\n\n"
    
    "MANDATORY TEACHING STRUCTURE - follow this EXACTLY:\n"
    "For EVERY new concept:\n"
    "1. SHOW a matplotlib visualization FIRST (before any text explanation)\n"
    "2. Then explain what the student is SEEING in the plot\n"
    "3. Then ask ONE question about what they see\n\n"
    
    "CRITICAL RULES:\n"
    "- NEVER explain a concept with text alone. ALWAYS include a python code block with matplotlib code.\n"
    "- If you mention design space, loads, supports, or material - SHOW them in a diagram first.\n"
    "- Every response must contain either a code block with matplotlib OR a [PRACTICE] exercise.\n"
    "- Use [PRACTICE] for coding exercises only. Use [QUIZ] for multiple choice.\n"
    "- Keep text under 100 words. The visual does the teaching.\n"
    "- One concept per message. Ask one question. Stop.\n\n"
    
    "VISUAL REQUIREMENTS:\n"
    "- Use fig, ax = plt.subplots(figsize=(8,4)) for good proportions\n"
    "- Always add title, axis labels, and annotations\n"
    "- Use colors: blue for material, red for loads, gray for void\n"
    "- For topology optimization: show the domain, loads (arrows), and fixed supports clearly\n\n"
    
    "EXAMPLE of correct first response:\n"
    "```python\nimport matplotlib.pyplot as plt\nfig, ax = plt.subplots(figsize=(8,4))\nrect = plt.Rectangle((1,1), 6, 2, fill=False, edgecolor='blue', linewidth=2)\nax.add_patch(rect)\nax.annotate('LOAD', xy=(7,2), fontsize=12, color='red', weight='bold')\nax.arrow(7.5, 2, -0.5, 0, head_width=0.15, color='red', linewidth=2)\nax.annotate('FIXED', xy=(1, 2.2), fontsize=10, color='gray')\nax.add_patch(plt.Rectangle((0.8, 0.8), 0.4, 2.4, color='gray', alpha=0.7))\nax.set_xlim(0, 9)\nax.set_ylim(0, 4)\nax.set_title('Design Space: Cantilever Beam')\nax.set_xlabel('X')\nax.set_ylabel('Y')\nplt.show()\n```\n"
    "This is the design space. The gray area is fixed. The red arrow shows where force pushes. "
    "The algorithm decides where to put material inside the blue box. "
    "What does the gray region represent?\n\n"
    
    "START: Ask about coding experience. Then show the design space concept with a diagram like above."
)

def test_api():
    if not KEY:
        return None, "No API key in Secrets"
    models = ["step-5-preview", "step-5", "step-3", "step-2", "step-1-8k", "step-1-32k"]
    for m in models:
        try:
            c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=10)
            r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "Say OK"}], max_tokens=5)
            if r.choices[0].message.content:
                if not st.session_state.model:
                    st.session_state.model = m
                return m, "Connected: " + m
        except Exception as e:
            err = str(e)
            if "401" in err:
                return None, "Invalid API key"
    return None, "No model works"

def ask_ai(msg, visual_feedback=None):
    if not KEY:
        return "No API key found"
    if not st.session_state.model:
        model, status = test_api()
        if not model:
            return "ERROR: " + status
    try:
        c = OpenAI(api_key=KEY, base_url=API_BASE, timeout=60)
        chat = [{"role": "system", "content": PROMPT}]
        for x in st.session_state.msgs:
            chat.append({"role": x.get("role", "user"), "content": x.get("content", "")})
        if visual_feedback:
            chat.append({"role": "user", "content": "[STUDENT SEES] " + visual_feedback})
            chat.append({"role": "assistant", "content": "Acknowledged."})
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
        return "Empty response"
    except Exception as e:
        err = str(e)
        if "404" in err:
            st.session_state.model = None
            st.session_state.tested = False
            return "Model not found. Click Auto-Test."
        return "Error: " + err[:100]

def describe_figure(fig):
    if fig is None:
        return "No plot"
    parts = []
    try:
        for ax in fig.axes:
            if ax.get_title():
                parts.append("Title: " + ax.get_title())
            if ax.get_xlabel():
                parts.append("X: " + ax.get_xlabel())
            if ax.get_ylabel():
                parts.append("Y: " + ax.get_ylabel())
            lines = ax.get_lines()
            if lines:
                parts.append(str(len(lines)) + " lines")
                for j, line in enumerate(lines):
                    ydata = line.get_ydata()
                    if len(ydata) > 1:
                        trend = "up" if ydata[-1] > ydata[0] else "down" if ydata[-1] < ydata[0] else "flat"
                        parts.append("line " + str(j+1) + " " + trend)
            images = ax.get_images()
            if images:
                for img in images:
                    try:
                        data = np.asarray(img.get_array())
                        parts.append("grid " + str(data.shape[0]) + "x" + str(data.shape[1]))
                        dark = float((data < 0.3).sum()) / data.size * 100
                        parts.append(str(int(dark)) + "% dark")
                    except:
                        pass
            patches = ax.patches
            if patches:
                parts.append(str(len(patches)) + " shapes")
            texts = ax.texts
            if texts:
                for t in texts:
                    if t.get_text():
                        parts.append("label: " + t.get_text())
        return " | ".join(parts) if parts else "Plot rendered"
    except:
        return "Plot rendered"

def verify_plot(fig):
    """Check the plot actually has visual content."""
    if fig is None:
        return False, "No figure created"
    if not fig.axes:
        return False, "No axes"
    for ax in fig.axes:
        if ax.get_lines() or ax.get_images() or ax.patches or ax.collections:
            return True, "OK"
    return False, "Empty plot"

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
                ok, status = verify_plot(fig)
                if ok:
                    desc = describe_figure(fig)
                else:
                    desc = "WARNING: " + status
                plt.close("all")
        except:
            pass
        return out, err, fig, desc
    except:
        sys.stdout, sys.stderr = old_out, old_err
        return cap_out.getvalue(), traceback.format_exc(), None, ""

def clean(t):
    if not t:
        return ""
    return re.sub(r"\[PRACTICE\].*", "", t, flags=re.DOTALL).strip()

def extract_code_blocks(text):
    return [m.strip() for m in re.findall(r"```python\s*\n(.*?)```", text, flags=re.DOTALL)]

def has_matplotlib(code):
    return "plt." in code or "matplotlib" in code or "pyplot" in code

st.set_page_config(page_title="Studio", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, .stApp {
    background: #0a0a0a;
    color: #fff;
    font-family: 'Inter', -apple-system, sans-serif;
    height: 100vh;
    overflow: hidden;
}

#MainMenu, footer, header, [data-testid="stSidebar"], [data-testid="stToolbar"] {
    display: none !important;
}

.block-container {
    max-width: 720px;
    height: calc(100vh - 1rem);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding-top: 0.5rem;
    padding-bottom: 0;
    margin: 0 auto;
}

.title-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0 0.75rem 0;
    border-bottom: 1px solid #1a1a1a;
    flex-shrink: 0;
}

.title-bar h1 {
    font-size: 1.5rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.04em;
    margin: 0;
}

.reset-btn {
    background: #1a1a1a;
    color: #666;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 0.375rem 0.75rem;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    font-family: 'Inter', sans-serif;
    transition: all 0.15s;
}

.reset-btn:hover {
    color: #ff453a;
    border-color: #ff453a;
    background: #1a0d0d;
}

.chat-scroll {
    flex-grow: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0.5rem 0.25rem 0.5rem 0;
    scrollbar-width: thin;
    scrollbar-color: #2a2a2a transparent;
}

.chat-scroll::-webkit-scrollbar {
    width: 4px;
}
.chat-scroll::-webkit-scrollbar-track {
    background: transparent;
}
.chat-scroll::-webkit-scrollbar-thumb {
    background: #2a2a2a;
    border-radius: 2px;
}

[data-testid="stChatMessage"] {
    background: transparent;
    border: none;
    padding: 0.25rem 0;
    margin: 0;
}
[data-testid="stChatMessageAvatar"] { display: none; }
[data-testid="stChatMessageContent"] {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    border-bottom-left-radius: 4px;
    padding: 0.75rem 1rem;
    font-size: 0.9rem;
    line-height: 1.6;
    color: #e0e0e0;
}
[data-testid="stChatMessage"] pre {
    background: #0a0a0a !important;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 0.75rem;
    font-size: 0.8rem;
    max-width: 100%;
    overflow-x: auto;
}
[data-testid="stChatMessage"] code {
    background: #2a2a2a;
    color: #7dd3fc;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 0.85em;
}
[data-testid="stChatMessage"] pre code { background: transparent; padding: 0; color: inherit; }
[data-testid="stChatMessage"] strong { color: #fff; font-weight: 600; }

[data-testid="stChatInput"] {
    flex-shrink: 0;
    padding: 0.5rem 0 0.25rem 0;
    border-top: 1px solid #1a1a1a;
    background: #0a0a0a;
}
[data-testid="stChatInput"] textarea {
    background: #141414 !important;
    border: 1px solid #333 !important;
    border-radius: 18px !important;
    color: #fff !important;
    font-size: 0.95rem !important;
    padding: 0.875rem 1.125rem !important;
    min-height: 48px !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stChatInput"] textarea:focus { border-color: #0a84ff !important; }
[data-testid="stChatInput"] textarea::placeholder { color: #555 !important; }

.stButton > button {
    background: #0a84ff;
    color: #fff;
    border: none;
    border-radius: 12px;
    padding: 0.7rem 1.25rem;
    font-weight: 600;
    font-size: 0.9rem;
    font-family: 'Inter', sans-serif;
    width: 100%;
}
.stButton > button:hover { background: #409cff; }

.stTextArea textarea {
    background: #0a0a0a !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 12px !important;
    font-family: 'SF Mono', monospace !important;
    color: #e0e0e0 !important;
    font-size: 0.875rem !important;
    padding: 0.875rem !important;
    min-height: 140px !important;
}

.card {
    background: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 16px;
    padding: 1.25rem;
    margin: 0.5rem 0;
    text-align: center;
}
.card h3 { color: #fff; font-size: 1.05rem; font-weight: 700; margin: 0 0 0.25rem 0; }
.card p { color: #777; font-size: 0.8rem; margin: 0; }

.good {
    background: #0d0d0d;
    border: 1px solid rgba(48,209,88,.3);
    border-radius: 10px;
    padding: 0.75rem;
    font-family: monospace;
    font-size: 0.8rem;
    color: #30d158;
    white-space: pre-wrap;
    margin: 0.5rem 0;
}
.bad {
    background: #1a0d0d;
    border: 1px solid rgba(255,69,58,.3);
    border-radius: 10px;
    padding: 0.75rem;
    font-family: monospace;
    font-size: 0.8rem;
    color: #ff453a;
    white-space: pre-wrap;
    margin: 0.5rem 0;
}

.plot-box {
    background: #141414;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    padding: 0.5rem;
    margin: 0.75rem 0;
}
.plot-label {
    font-size: 0.65rem;
    font-weight: 700;
    color: #0a84ff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0.25rem 0.5rem 0 0.5rem;
}

.ai-sees {
    background: #0d1520;
    border: 1px solid rgba(10,132,255,.2);
    border-radius: 8px;
    padding: 0.4rem 0.6rem;
    margin: 0.25rem 0 0.5rem 0.5rem;
    font-size: 0.7rem;
    color: #7dd3fc;
    font-style: italic;
}

.label {
    font-size: 0.65rem;
    font-weight: 700;
    color: #0a84ff;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0.75rem 0 0.375rem 0;
}

.status-bar {
    flex-shrink: 0;
    padding: 0.375rem 0;
    font-size: 0.7rem;
    color: #555;
    text-align: center;
}

.stTextInput input {
    background: #141414 !important;
    border: 1px solid #2a2a2a !important;
    border-radius: 10px !important;
    color: #fff !important;
    padding: 0.5rem 0.75rem !important;
}
.stTextInput input:focus { border-color: #0a84ff !important; }

[data-testid="stInfo"] { background: #0d0d0d; border: 1px solid #0a84ff; border-radius: 10px; color: #a0c4ff; }
[data-testid="stSpinner"] > div { border-top-color: #0a84ff !important; }

.mode-badge {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    margin-left: 0.5rem;
}
.mode-viz { background: #0a84ff20; color: #7dd3fc; }
.mode-code { background: #30d15820; color: #30d158; }
.mode-quiz { background: #ffd60a20; color: #ffd60a; }
</style>
""", unsafe_allow_html=True)

# ============ LAYOUT ============

# Title bar with reset
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

# Status bar
if st.session_state.model:
    st.markdown('<p style="color:#30d158;font-size:0.7rem;text-align:center;margin:0.25rem 0;">Connected: ' + st.session_state.model + '</p>', unsafe_allow_html=True)
elif KEY:
    st.markdown('<p style="color:#ffd60a;font-size:0.7rem;text-align:center;margin:0.25rem 0;">Set model below to start</p>', unsafe_allow_html=True)
else:
    st.markdown('<p style="color:#ff453a;font-size:0.7rem;text-align:center;margin:0.25rem 0;">No API key in Secrets</p>', unsafe_allow_html=True)

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

# ============ TRACK SELECTION ============
if len(st.session_state.msgs) == 0 and st.session_state.tested:
    st.markdown('<div class="card"><h3>Topology Optimization</h3><p>Build a structural solver with visual demos</p></div>', unsafe_allow_html=True)
    if st.button("Start Topology Optimization", type="primary"):
        st.session_state.start = "topo"
    st.markdown('<div class="card"><h3>System Design</h3><p>Design real systems with code</p></div>', unsafe_allow_html=True)
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

# ============ CHAT AREA (Scrollable) ============
chat_area = st.container()

with chat_area:
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
                        else:
                            st.markdown('<div class="bad">Plot verification failed: ' + status + '</div>', unsafe_allow_html=True)

# ============ CODE SANDBOX ============
if st.session_state.editor:
    st.markdown('<div class="label">Practice <span class="mode-badge mode-code">CODE</span></div>', unsafe_allow_html=True)
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
                    sub += "My plot shows: " + st.session_state.plot_desc + "\n"
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

# ============ CHAT INPUT (Fixed at bottom) ============
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
                    vf = "; ".join(st.session_state.visual_log[-3:]) if st.session_state.visual_log else None
                    reply = ask_ai(msg, visual_feedback=vf)
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
