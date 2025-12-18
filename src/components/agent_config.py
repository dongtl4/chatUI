import streamlit as st
import os
import src.core.agent as agent_logic

def get_default_settings():
    """Returns default settings based on environment variables."""
    # Priority: OpenAI -> DeepSeek -> Ollama (Local)
    if os.getenv("DEEPSEEK_API_KEY"):
        return {
            "provider": "DeepSeek",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "id": "deepseek-chat",
            "name": "DeepSeek Agent"
        }
    elif os.getenv("OPENAI_API_KEY"):
        return {
            "provider": "OpenAI",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "id": "gpt-4o",
            "name": "OpenAI Agent"
        }
    else:
        # Default fallback
        return {
            "provider": "Ollama",
            "host": "http://10.10.128.140:11434",
            "id": "llama3.2",
            "name": "Ollama Agent"
        }

def auto_initialize():
    """
    Called by main.py on startup. 
    Checks if a model is already loaded; if not, tries to load one from defaults.
    """
    if "agent_instructions" not in st.session_state:
        st.session_state["agent_instructions"] = "You are a helpful assistant."

    if not st.session_state.get('model'):
        defaults = get_default_settings()
        
        # Only try to initialize if we have what we need (simple check)
        ready_to_init = True
        if defaults["provider"] != "Ollama" and not defaults.get("api_key"):
            ready_to_init = False
            
        if ready_to_init:
            try:
                # Filter out 'provider' key for the kwargs
                params = {k: v for k, v in defaults.items() if k != "provider"}
                st.session_state['model'] = agent_logic.create_model(defaults["provider"], **params)
            except Exception:
                pass # Fail silently on auto-init; user can fix in UI

def render():
    """Renders the Configuration UI."""
    st.header("🤖 Agent Configuration")
    
    current_model = st.session_state.get('model')
    if current_model:
        st.success(f"✅ Active Model: **{current_model.name}** ({current_model.id})")
    else:
        st.warning("No model currently active. Please configure below.")

    st.divider()

    # Load defaults for the UI form
    defaults = get_default_settings()
    
    # Provider Selection
    options = ["OpenAI", "DeepSeek", "Ollama"]
    # Try to set the index to the detected default provider
    try:
        def_index = options.index(defaults["provider"])
    except ValueError:
        def_index = 2 # Ollama

    model_provider = st.selectbox("Switch Provider", options, index=def_index)
    
    # Form Inputs
    model_params = {}
    
    # If the user selected the provider that matches our defaults, pre-fill values
    is_default_provider = (model_provider == defaults["provider"])
    
    if model_provider in ["OpenAI", "DeepSeek"]:
        def_key = defaults.get("api_key", "") if is_default_provider else ""
        def_id = defaults.get("id", "gpt-4o") if is_default_provider else ("gpt-4o" if model_provider == "OpenAI" else "deepseek-chat")
        
        model_params["api_key"] = st.text_input(f"{model_provider} API Key", type="password", value=def_key)
        model_params["id"] = st.text_input("Model ID", value=def_id)
        model_params["name"] = st.text_input("Model Name", value=f"{model_provider} Agent")
        
    elif model_provider == "Ollama":
        def_host = defaults.get("host", "http://10.10.128.140:11434") if is_default_provider else "http://10.10.128.140:11434"
        def_id = defaults.get("id", "llama3.2") if is_default_provider else "llama3.2"
        
        model_params["host"] = st.text_input("Host", value=def_host)
        model_params["id"] = st.text_input("Model ID", value=def_id)
        model_params["name"] = st.text_input("Model Name", value="Ollama Agent")

    st.subheader("Instructions")
    st.text_area("System Prompt", key="agent_instructions", height=150)

    if st.button("Update Agent Settings", type="primary"):
        try:
            new_model = agent_logic.create_model(model_provider, **model_params)
            if new_model:
                st.session_state['model'] = new_model
                # st.session_state["history"] = [] # Optional: Clear history on switch
                st.success(f"Switched to {model_provider} model!")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to create model: {e}")