import streamlit as st
from openai import OpenAI
import os
import io
import sys
import contextlib
import traceback
import time
import re
import json

# ============ CONFIG ============
API_BASE_URL = "https://api.stepfun.ai/step_plan/v1"
MODEL_NAME = "step-5-preview"
HISTORY_FILE = "chat_history.json"

# ============ INITIALIZE SESSION STATE (Always, unconditionally) ============
DEFAULTS = {
    "messages": [],
    "concepts_learned": [],
    "exercises_completed": 0,
    "current_track": None,
    "show_code_editor": False,
    "code_exercise": "",
    "code_content": "# Type your code here\n",
    "code_output": "",
    "code_error": "",
    "code_ran": False,
    "current_plot": None,
    "has_plot": False,
    "show_quiz": False,
    "quiz_question": "",
    "quiz_options": [],
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ============ PERSISTENCE ============
def save_history():
    """Save state to file. Only saves serializable data."""
    try:
        data = {
            "messages": st.session_state.get("messages", []),
            "concepts_learned": st.session_state.get("concepts_learned", []),
            "exercises_completed": st.session_state.get("exercises_completed", 0),
            "current_track": st.session_state.get("current_track"),
            "show_code_editor": st.session_state.get("show_code_editor", False),
            "code_exercise": st.session_state.get("code_exercise", ""),
            "code_content": st.session_state.get("code_content", ""),
            "code_output": st.session_state.get("code_output", ""),
            "code_error": st.session_state.get("code_error", ""),
            "code_ran": st.session_state.get("code_ran", False),
            "has_plot": st.session_state.get("has_plot", False),
        }
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
    except Exception:
        pass

def load_history():
    """Load state from file if it exists."""
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
            for key, value in data.items():
                if key in st.session_state:
                    st.session_state[key] = value
            # Reset non-serializable items
            st.session_state.current_plot = None
            st.session_state.has_plot = False
            return True
    except Exception:
        pass
    return False

# Load on first run
if not st.session_state.get("loaded", False):
    load_history()
    st.session_state.loaded = True

def clear_all():
    """Reset everything."""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
    except Exception:
        pass
    for key, default in DEFAULTS.items():
        st.session_state[key] = default
    st.session_state.loaded = True

# ============ API KEY ============
API_KEY = ""
try:
    API_KEY = st.secrets.get("STEPFUN_API_KEY", os.environ.get("STEPFUN_API_KEY", ""))
except Exception:
    try:
        API_KEY = os.environ.get("STEPFUN_API_KEY", "")
    except Exception:
        API_KEY = ""

# ============ MENTOR PROMPT ============
MENTOR_PROMPT = """
You are a senior engineering mentor. You teach exactly two subjects:
1. **Topology Optimization** — structural engineering, SIMP method, FEA
2. **System Design** — software architecture, real systems

The student may have zero coding experience. You teach everything needed.

## ABSOLUTE RULE — NEVER ASK TO IMAGINE

The student CANNOT learn through mental visualization. They MUST see everything.

FORBIDDEN: "Imagine...", "Picture...", "Visualize...", "Think about what would..."

INSTEAD, ALWAYS:
- Show matplotlib code that draws the concept
- Print actual data and output
- Give concrete examples with real numbers
- Use ASCII diagrams when plots aren't possible
- Provide runnable code that demonstrates

Example:
❌ WRONG: "Imagine a cantilever beam fixed at one end."
✅ RIGHT: "Here's a cantilever beam. Run this code:
```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(8, 3))
ax.fill_between([0, 8], [0, 0], [1, 1], color='#0A84FF', alpha=0.3)
ax.plot([0, 8], [1, 1], 'b-', linewidth=2)
ax.plot([0, 8], [0, 0], 'b-', linewidth=2)
ax.plot([8, 8], [0, 1], 'b-', linewidth=2)
ax.add_patch(plt.Rectangle((0, 0), 0.3, 1, color='red'))
ax.set_title('Cantilever Beam — Fixed (red) Left, Load Right')
plt.show()
