st.markdown('<div class="section-label">📝 Practice</div>', unsafe_allow_html=True)

st.info(f"**Task:** {st.session_state.code_exercise}")

code = st.text_area(
    "",
    value=st.session_state.code_content,
    height=180,
    key="code_editor",
    label_visibility="collapsed",
    placeholder="# Type your Python code here..."
)

col1, col2 = st.columns(2)

with col1:
    if st.button("▶  Run", use_container_width=True, type="primary"):
        st.session_state.code_content = code
        with st.spinner("Running..."):
            output, error, has_fig, fig = execute_code(code)
            st.session_state.code_output = output
            st.session_state.code_error = error
            st.session_state.code_ran = True
            st.session_state.has_plot = has_fig
            st.session_state.current_plot = fig
            save_history()

with col2:
    if st.button("✓  Submit", use_container_width=True):
        if not st.session_state.code_ran:
            st.warning("Run your code first.")
        else:
            submission = f"I completed the exercise.\n\nMy code:\n```python\n{code}\n```\n\n"
            if st.session_state.code_output:
                submission += f"Output:\n```\n{st.session_state.code_output}\n```\n"
            if st.session_state.code_error and "Traceback" in st.session_state.code_error:
                submission += f"Error — help me fix it:\n```\n{st.session_state.code_error}\n```"
            else:
                submission += "Please review my work."
            
            st.session_state.messages.append({"role": "user", "content": submission})
            st.session_state.exercises_completed += 1
            st.session_state.show_code_editor = False
            
            # Render as right-aligned user message
            _, col = st.columns([0.35, 0.65])
            with col:
                with st.chat_message("user"):
                    st.write(submission)
            
            # Get AI response
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = get_ai_response_streaming(submission, placeholder)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            save_history()
            st.rerun()

if st.session_state.code_ran:
    if st.session_state.code_output:
        st.markdown(f'<div class="output-box">✅ {st.session_state.code_output}</div>', unsafe_allow_html=True)
    if st.session_state.code_error and "Traceback" in st.session_state.code_error:
        error_lines = st.session_state.code_error.split('\n')
        clean_error = '\n'.join(error_lines[-5:])
        st.markdown(f'<div class="error-box">❌ {clean_error}</div>', unsafe_allow_html=True)
