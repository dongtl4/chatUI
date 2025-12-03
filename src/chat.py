import streamlit as st
from uuid import uuid4
import history

def render_current_chat_container(placeholder):
    """Renders the message currently being streamed."""
    placeholder.empty()
    if not st.session_state.get("current_chat"):
        return

    # Calculate index for the current running message
    # Since st.session_state.history includes the current one being built, 
    # the index is len(history) - 1
    current_idx = len(st.session_state.get("history", [])) - 1
    if current_idx < 0: current_idx = 0

    with placeholder.container():
        # Inject Anchor for the current streaming message
        st.markdown(f"<div id='msg-{current_idx}'></div>", unsafe_allow_html=True)
        
        if st.session_state["current_chat"]:
            msg_pair = st.session_state["current_chat"][-1]
            with st.chat_message("user"):
                st.markdown(msg_pair.get("user", ""))
            with st.chat_message("assistant"):
                st.markdown(msg_pair.get("assistant", "") or "_(thinking...)_")

def handle_chat_run(agent, config, history_db):
    """Main execution logic."""
    
    st.subheader("🤔 Ask a Question")
    current_chat_placeholder = st.container().empty()

    with st.form("ask_form", clear_on_submit=True):
        query = st.text_area("Your question:", height=100)
        submitted = st.form_submit_button("🚀 Get Answer", type="primary")

    if submitted and query:
        # Update UI with the new pair structure
        st.session_state["current_chat"] = [
            {"user": query, "assistant": ""} 
        ]
        
        # Optimistic update of history
        st.session_state["history"].append({
            "user": query,
            "assistant": "",
        })
        st.session_state.running = str(uuid4())
        st.rerun()

    if st.session_state.get('running', False):
        token = st.session_state['running']
        if token != 'in_progress':
            st.session_state['running'] = 'in_progress'
            render_current_chat_container(current_chat_placeholder)

            # --- CONTEXT CONSTRUCTION ---
            original_query = query if 'query' in locals() else st.session_state["current_chat"][-1]["user"]
            
            final_prompt = original_query
            
            if config["use_history"]:
                final_prompt = f"User's current question: {original_query}\n\n"
                history_context_str = ""
                
                # Get history from state (excluding current running item)
                hist_source = st.session_state["history"][:-1]
                if not config["use_full_history"]:
                     hist_source = hist_source[-config["history_length"]:]

                for msg in hist_source:
                    history_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
                
                final_prompt += f"---Conversation history (Context only, do not save):\n{history_context_str}\n\n"

            # --- STREAMING ---
            full_response = ""
            try:
                for chunk in agent.run(final_prompt, stream=True):
                    if hasattr(chunk, 'event') and chunk.event == "RunContent":
                        if hasattr(chunk, 'content') and chunk.content:
                            full_response += chunk.content
                            st.session_state["current_chat"][-1]["assistant"] = full_response
                            render_current_chat_container(current_chat_placeholder)
            finally:
                st.session_state.running = None
                
                # saving current chat exchange
                history.save_exchange_to_db(
                    history_db, 
                    st.session_state["session_id"], 
                    original_query, 
                    full_response
                )
                
                # Finalize UI state
                st.session_state["history"][-1]["assistant"] = full_response
                st.rerun()