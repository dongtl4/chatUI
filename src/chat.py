import streamlit as st
import streamlit.components.v1 as components
from uuid import uuid4
import history

def scroll_to_anchor():
    """
    Injects JS to scroll specifically to the 'current_response_anchor' element.
    This is more reliable than scrolling to the bottom of the page.
    """
    js = """
    <script>
        // Wait slightly for the DOM to update
        setTimeout(function() {
            // Target the specific anchor ID we placed in the app
            var element = window.parent.document.getElementById('current_response_anchor');
            if (element) {
                // Scroll the element into view. 
                // 'block: start' tries to align the top of the element with the top of the viewport
                element.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        }, 100);
    </script>
    """
    components.html(js, height=0, width=0)

def render_current_chat_container(placeholder):
    """Renders the message currently being streamed."""
    placeholder.empty()
    if not st.session_state.get("current_chat"):
        return

    current_idx = len(st.session_state.get("history", [])) - 1
    if current_idx < 0: current_idx = 0

    with placeholder.container():
        st.markdown(f"<div id='msg-{current_idx}'></div>", unsafe_allow_html=True)
        
        if st.session_state["current_chat"]:
            msg_pair = st.session_state["current_chat"][-1]
            with st.chat_message("user"):
                st.markdown(msg_pair.get("user", ""))
            with st.chat_message("assistant"):
                st.markdown(msg_pair.get("assistant", "") or "_(thinking...)_")

def handle_chat_run(agent, config, history_db):
    """Main execution logic."""
    
    # 1. Place the Anchor Marker HERE, right before the streaming container.
    # The JS will hunt for this ID.
    st.markdown("<div id='current_response_anchor'></div>", unsafe_allow_html=True)

    # Placeholder for the streaming response
    current_chat_placeholder = st.container().empty()

    # --- INPUT AREA (Fixed at Bottom) ---
    query = st.chat_input("Ask a question...")

    if query:
        st.session_state["current_chat"] = [
            {"user": query, "assistant": ""} 
        ]
        st.session_state["history"].append({
            "user": query,
            "assistant": "",
            "marked": False 
        })
        st.session_state.running = str(uuid4())
        st.rerun()

    # --- PROCESSING LOGIC ---
    if st.session_state.get('running', False):
        token = st.session_state['running']
        if token != 'in_progress':
            st.session_state['running'] = 'in_progress'
            
            # Execute the scroll immediately so the user sees the start of the response area
            scroll_to_anchor()
            
            render_current_chat_container(current_chat_placeholder)

            # --- CONTEXT CONSTRUCTION ---
            original_query = st.session_state["current_chat"][-1]["user"]
            final_prompt = ""

            # 1. Add Marked Context (if enabled)
            if config.get("use_marked_context", False):
                marked_context_str = ""
                existing_history = st.session_state["history"][:-1]
                
                for msg in existing_history:
                    if msg.get("marked", False):
                        marked_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n---\n"
                
                if marked_context_str:
                    final_prompt += f"!!! IMPORTANT CONTEXT (Explicitly marked by user) !!!\n{marked_context_str}\n!!! END IMPORTANT CONTEXT !!!\n\n"

            # 2. Add Standard History (if enabled)
            if config["use_history"]:
                final_prompt += f"User's current question: {original_query}\n\n"
                history_context_str = ""
                
                hist_source = st.session_state["history"][:-1]
                if not config["use_full_history"]:
                     hist_source = hist_source[-config["history_length"]:]

                for msg in hist_source:
                    history_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
                
                final_prompt += f"---Conversation history (Context only, do not save):\n{history_context_str}\n\n"
            else:
                final_prompt += original_query

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
                
                history.save_exchange_to_db(
                    history_db, 
                    st.session_state["session_id"], 
                    original_query, 
                    full_response
                )
                
                st.session_state["history"][-1]["assistant"] = full_response
                
                st.session_state.history = history.load_history_from_custom_db(
                    history_db, 
                    st.session_state.get("session_id")
                )

                st.rerun()