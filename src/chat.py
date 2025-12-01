import streamlit as st
from uuid import uuid4
import history

def render_current_chat_container(placeholder):
    """Renders the message currently being streamed."""
    placeholder.empty()
    if not st.session_state.get("current_chat"):
        return

    with placeholder.container():
        for msg in st.session_state["current_chat"][-2:]:
            role = "user" if msg["role"] == "user" else "assistant"
            with st.chat_message(role):
                st.markdown(msg.get("text", "") or f"_(no {role} message)_")

def handle_chat_run(agent, config, history_db):
    """Main execution logic."""
    
    st.subheader("🤔 Ask a Question")
    current_chat_placeholder = st.container().empty()

    with st.form("ask_form", clear_on_submit=True):
        query = st.text_area("Your question:", height=100)
        submitted = st.form_submit_button("🚀 Get Answer", type="primary")

    if submitted and query:
        # Update UI immediately with CLEAN query
        st.session_state["current_chat"] = [
            {"role": "user", "text": query},
            {"role": "assistant", "text": ""} 
        ]
        # Optimistic update of history
        st.session_state["history"].append({
            "user": query,
            "assistant": "",
            "marked": False
        })
        st.session_state.running = str(uuid4())
        st.rerun()

    if st.session_state.get('running', False):
        token = st.session_state['running']
        if token != 'in_progress':
            st.session_state['running'] = 'in_progress'
            render_current_chat_container(current_chat_placeholder)

            # --- CONTEXT CONSTRUCTION ---
            # Retrieve the original clean query
            original_query = query if 'query' in locals() else st.session_state["current_chat"][-2]["text"]
            
            # Create the "polluted" prompt for the Agent only
            final_prompt = original_query
            
            if config["use_history"]:
                final_prompt = f"User's current question: {original_query}\n\n"
                history_context_str = ""
                
                # Get history from state
                hist_source = st.session_state["history"][:-1]
                if not config["use_full_history"]:
                     hist_source = hist_source[-config["history_length"]:]

                for msg in hist_source:
                    history_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
                
                final_prompt += f"---Conversation history (Context only, do not save):\n{history_context_str}\n\n"

            # --- STREAMING ---
            full_response = ""
            try:
                # Agent runs with the full context prompt
                for chunk in agent.run(final_prompt, stream=True):
                    if hasattr(chunk, 'event') and chunk.event == "RunContent":
                        if hasattr(chunk, 'content') and chunk.content:
                            full_response += chunk.content
                            st.session_state["current_chat"][-1]["text"] = full_response
                            render_current_chat_container(current_chat_placeholder)
            finally:
                st.session_state.running = None
                
                # --- MANUAL SAVE (CLEAN DATA) ---
                # Save the original user query, not the history-padded prompt
                history.save_message_to_db(
                    history_db, 
                    st.session_state["session_id"], 
                    "user", 
                    original_query
                )
                
                # Save the assistant response
                history.save_message_to_db(
                    history_db, 
                    st.session_state["session_id"], 
                    "assistant", 
                    full_response
                )
                
                # Finalize UI state
                st.session_state["history"][-1]["assistant"] = full_response
                st.rerun()