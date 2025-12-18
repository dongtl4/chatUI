import streamlit as st
from src.core import db as db_logic

def render_sidebar(history_db):
    """
    Renders the sidebar navigation and updates the 'current_view' in session state.
    """
    
    # Ensure current_view defaults to chat
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "chat_interface"

    with st.sidebar:
        st.header("NAVIGATION")
        if st.session_state.get("session_id"):
            st.caption(f"Session: {st.session_state.get('session_id')}")
        st.divider()

        if st.button("💬 Chat Interface", use_container_width=True):
            st.session_state["current_view"] = "chat_interface"

        # --- 1. Chat Expander ---
        with st.expander("Context", expanded=False):
            if st.button("⚙️ Context Settings", use_container_width=True):
                st.session_state["current_view"] = "context_config"

        # --- 2. Agent Expander ---
        with st.expander("Agent", expanded=False):
             if st.button("🤖 Agent Configuration", use_container_width=True):
                st.session_state["current_view"] = "agent_config"

        # --- 3. Knowledge Expander ---
        with st.expander("Knowledge", expanded=False):
            if st.button("🔌 Connect Database", use_container_width=True):
                st.session_state["current_view"] = "knowledge_config"
            if st.button("📚 Manage Files", use_container_width=True):
                st.session_state["current_view"] = "knowledge_ui"

        # --- 4. Current Conversation Expander ---
        with st.expander("Current Conversation", expanded=True):
            if st.session_state.get("history"):
                display_history = st.session_state.history
                for idx, item in enumerate(display_history):
                    c_mark, c_link = st.columns([0.2, 0.8])
                    with c_mark:
                        msg_id = item.get("id")
                        if msg_id:
                            is_marked = st.checkbox(
                                "Mark", 
                                value=item.get("marked", False), 
                                key=f"mark_chk_{msg_id}", 
                                label_visibility="collapsed"
                            )
                            if is_marked != item.get("marked", False):
                                db_logic.toggle_exchange_marker(history_db, msg_id, is_marked)
                                item["marked"] = is_marked
                                st.rerun()
                    with c_link:
                        user_text = item.get("user", "")
                        label = (user_text[:20] + '...') if len(user_text) > 20 else user_text or f"Msg {idx+1}"
                        st.markdown(f"[{idx + 1}. {label}](#msg-{idx})")
            else:
                st.caption("Start a conversation to see navigation.")