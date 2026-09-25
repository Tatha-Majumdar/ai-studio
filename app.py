def call_api(user_message):
    """Try the API with different models until one works."""
    
    if not API_KEY:
        return "ERROR: No API key. Add STEPFUN_API_KEY in Secrets."
    
    # Try each model
    errors = []
    
    for model in MODEL_OPTIONS:
        try:
            client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
            
            api_messages = [{"role": "system", "content": MENTOR_PROMPT}]
            
            for msg in st.session_state.get("messages", []):
                api_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            api_messages.append({"role": "user", "content": user_message})
            
            response = client.chat.completions.create(
                model=model,
                messages=api_messages,
                max_tokens=4000,
                temperature=0.6
            )
            
            reply = response.choices[0].message.content
            
            if reply and len(reply.strip()) > 0:
                # Success! Remember this model for next time
                st.session_state["working_model"] = model
                parse_ai_response(reply)
                return reply
            else:
                errors.append(model + ": empty response")
                
        except Exception as e:
            err = str(e)
            if "401" in err:
                return "ERROR: Invalid API key. Check your key in Secrets."
            elif "429" in err:
                return "ERROR: Rate limited. Wait 30 seconds and try again."
            elif "404" in err:
                errors.append(model + ": not found")
            else:
                errors.append(model + ": " + err[:50])
    
    # If all models failed
    return "ERROR: Could not get a response from any model.\n\nTried: " + ", ".join(errors)
