import streamlit as st
from uuid import uuid4

def render_current_chat_container(placeholder):
    """Renders the message currently being streamed."""
    # Clear previous rendering
    placeholder.empty()
    if not st.session_state.get("current_chat"):
        return

    with placeholder.container():
        # Render the last transaction (User + Assistant)
        for msg in st.session_state["current_chat"][-2:]:
            role = "user" if msg["role"] == "user" else "assistant"
            with st.chat_message(role):
                st.markdown(msg.get("text", "") or f"_(no {role} message)_")

def handle_chat_run(agent, config):
    """Main logic for handling input and running the agent."""
    
    st.subheader("🤔 Ask a Question")
    
    # Placeholder for live streaming update
    current_chat_placeholder = st.container().empty()

    # Form Input
    with st.form("ask_form", clear_on_submit=True):
        query = st.text_area("Your question:", height=100)
        submitted = st.form_submit_button("🚀 Get Answer", type="primary")

    if submitted:
        if query:
            # 1. Update Temporary UI State
            st.session_state["current_chat"] = [
                {"role": "user", "text": query},
                {"role": "assistant", "text": ""} # Placeholder for response
            ]
            
            # 2. Update Persistent History (Optimistic update)
            st.session_state["history"].append({
                "user": query,
                "assistant": "",
                "marked": False
            })
            
            # 3. Set running flag to trigger rerun loop
            st.session_state.running = str(uuid4())
            st.rerun()
        else:
            st.error("Please enter a question")

    # Execution Loop (Running state)
    if st.session_state.get('running', False):
        token = st.session_state['running']
        
        # Ensure we only process if in valid state
        if token != 'in_progress':
            st.session_state['running'] = 'in_progress'
            
            # Show the user message immediately
            render_current_chat_container(current_chat_placeholder)

            # Build Context String (if enabled in Sidebar)
            final_query = query if 'query' in locals() else st.session_state["current_chat"][-2]["text"]
            
            if config["use_history"]:
                final_query = f"User's current question: {final_query}\n\n"
                history_context_str = ""
                
                # Slicing history based on config
                hist_source = st.session_state["history"][:-1] # Exclude current incomplete msg
                if not config["use_full_history"]:
                     hist_source = hist_source[-config["history_length"]:]

                for msg in hist_source:
                    history_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
                
                final_query += f"---Conversation history:\n{history_context_str}\n\n"

            # Stream execution
            try:
                for chunk in agent.run(final_query, stream=True):
                    if hasattr(chunk, 'event') and chunk.event == "RunContent":
                        if hasattr(chunk, 'content') and chunk.content and isinstance(chunk.content, str):
                            # Append to temporary state
                            st.session_state["current_chat"][-1]["text"] += chunk.content
                            # Re-render
                            render_current_chat_container(current_chat_placeholder)
            finally:
                # Execution Done
                st.session_state.running = None
                # Commit final answer to history
                st.session_state["history"][-1]["assistant"] = st.session_state["current_chat"][-1]["text"]
                st.rerun()