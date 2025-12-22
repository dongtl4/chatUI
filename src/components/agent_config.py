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
        return {
            "provider": "Ollama",
            "host": "http://10.10.128.140:11434",
            "id": "llama3.2",
            "name": "Ollama Agent"
        }

def auto_initialize():
    """
    Called by main.py on startup. 
    Checks if agent params/prompt exist; if not, loads defaults.
    Then ensures the model object is initialized from those params.
    """
    # 1. Initialize System Prompt Structure
    if "system_prompt" not in st.session_state:
        st.session_state["system_prompt"] = {
            "description": "You are a helpful assistant.",
            "instructions": [],
            "additional_context": "",
            "expected_output": ""
        }

    # 2. Initialize Agent Parameters (Provider configs)
    if "agent_params" not in st.session_state:
        st.session_state["agent_params"] = get_default_settings()

    # 3. Initialize the Actual Model Object based on Params
    if not st.session_state.get('model'):
        params = st.session_state["agent_params"]
        try:
            # Prepare kwargs by excluding 'provider'
            model_kwargs = {k: v for k, v in params.items() if k != "provider"}
            
            # Create and store the model
            st.session_state['model'] = agent_logic.create_model(
                provider=params["provider"], 
                **model_kwargs
            )
        except Exception:
            # Fail silently on auto-init; user can fix in UI
            pass

def render():
    """Renders the Configuration UI based on stored session state."""
    st.header("🤖 Agent Configuration")
    
    current_model = st.session_state.get('model')
    if current_model:
        st.success(f"✅ Active Model: **{current_model.name}** ({current_model.id})")
    else:
        st.warning("No model currently active. Please configure below.")

    st.divider()

    # --- 1. Model Provider Settings ---
    current_params = st.session_state["agent_params"]
    options = ["OpenAI", "DeepSeek", "Ollama"]
    
    try:
        current_index = options.index(current_params.get("provider", "Ollama"))
    except ValueError:
        current_index = 2 
        
    selected_provider = st.selectbox("Switch Provider", options, index=current_index)
    
    # Defaults logic for UI inputs
    input_defaults = {}
    if selected_provider == current_params.get("provider"):
        input_defaults = current_params
    else:
        if selected_provider == "OpenAI":
            input_defaults = {"id": "gpt-4o", "name": "OpenAI Agent", "api_key": ""}
        elif selected_provider == "DeepSeek":
            input_defaults = {"id": "deepseek-chat", "name": "DeepSeek Agent", "api_key": ""}
        elif selected_provider == "Ollama":
            input_defaults = {"host": "http://10.10.128.140:11434", "id": "llama3.2", "name": "Ollama Agent"}

    new_params = {"provider": selected_provider}
    
    if selected_provider in ["OpenAI", "DeepSeek"]:
        new_params["api_key"] = st.text_input(f"{selected_provider} API Key", value=input_defaults.get("api_key", ""), type="password")
        new_params["id"] = st.text_input("Model ID", value=input_defaults.get("id", ""))
        new_params["name"] = st.text_input("Model Name", value=input_defaults.get("name", ""))
    elif selected_provider == "Ollama":
        new_params["host"] = st.text_input("Host", value=input_defaults.get("host", "http://10.10.128.140:11434"))
        new_params["id"] = st.text_input("Model ID", value=input_defaults.get("id", "llama3.2"))
        new_params["name"] = st.text_input("Model Name", value=input_defaults.get("name", "Ollama Agent"))

    st.divider()
    
    # --- 2. System Prompt Configuration ---
    st.subheader("📝 System Prompt Settings")
    
    current_prompt = st.session_state["system_prompt"]
    
    # Description
    new_description = st.text_area(
        "Description (A description of the Agent, added at the start of the system message)", 
        value=current_prompt.get("description", ""),
        height=70
    )
    
    # Instructions
    # Convert list back to string for editing
    instructions_list = current_prompt.get("instructions", [])
    instructions_str = "\n".join(instructions_list) if isinstance(instructions_list, list) else str(instructions_list)
    
    new_instructions_str = st.text_area(
        "Instructions (List of instructions added to the system prompt in <instructions> tags)", 
        value=instructions_str,
        height=150
    )
    
    # Additional Context
    new_context = st.text_area(
        "Additional Context (Additional context added to end of system message)", 
        value=current_prompt.get("additional_context", ""),
        height=70
    )
    
    # Expected Output
    new_output = st.text_area(
        "Expected Output (Provide the expected output from the Agent, added to end of system message)", 
        value=current_prompt.get("expected_output", ""),
        height=70
    )

    st.divider()

    # --- 3. Update Logic ---
    if st.button("Update Agent Settings", type="primary"):
        try:
            # 1. Save Agent Params
            st.session_state["agent_params"] = new_params
            
            # 2. Save System Prompt
            st.session_state["system_prompt"] = {
                "description": new_description,
                "instructions": [line for line in new_instructions_str.split('\n') if line.strip()],
                "additional_context": new_context,
                "expected_output": new_output
            }
            
            # 3. Re-create Model
            model_kwargs = {k: v for k, v in new_params.items() if k != "provider"}
            new_model = agent_logic.create_model(selected_provider, **model_kwargs)
            
            if new_model:
                st.session_state['model'] = new_model
                st.success(f"Settings updated and switched to {selected_provider} model!")
                st.rerun()
            else:
                st.error("Failed to create model object.")
                
        except Exception as e:
            st.error(f"Failed to update settings: {e}")