import streamlit as st
from uuid import uuid4
import src.core.db as db_logic

def auto_initialize():
    """Sets default session/context flags."""
    defaults = {
        "use_history": True,
        "use_full_history": True,
        "history_length": 5,
        "use_marked_context": True
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid4())
    
    if "history" not in st.session_state:
        st.session_state["history"] = []

def render(history_db):
    st.header("⚙️ History & Session Management")

    col_hist, col_sess = st.columns(2)

    with col_hist:
        st.subheader("History Chat Settings")
        st.session_state["use_history"] = st.checkbox("Use chat history for context", value=False)
        
        if st.session_state.get("use_history"):
            st.session_state["use_full_history"] = st.checkbox("Using full history", value=False)
            if not st.session_state.get("use_full_history"):
                st.session_state["history_length"] = st.number_input("Max history messages", min_value=1, max_value=20, value=5, step=1)
        
        st.session_state["use_marked_context"] = st.checkbox("Include MARKED messages as important context", value=True)

    with col_sess:
        st.subheader("Session Management")
        if "new_chat_mode" not in st.session_state:
            st.session_state["new_chat_mode"] = False

        sess_list = db_logic.load_session_list(history_db)
        current_id = st.session_state.get("session_id", "None")

        st.info(f"Current Session: **{current_id}**")

        if st.button("➕ New Chat Session"):
            st.session_state["new_chat_mode"] = True

        if st.session_state["new_chat_mode"]:
            new_id = st.text_input("Enter new Session ID", key="new_session_input")
            c1, c2 = st.columns([1, 1])
            if c1.button("Create"):
                if new_id and new_id not in sess_list:
                    st.session_state["session_id"] = new_id
                    st.session_state["history"] = []
                    st.session_state["new_chat_mode"] = False
                    st.rerun()
                else:
                    st.error("Invalid or duplicate ID")
            if c2.button("Cancel"):
                st.session_state["new_chat_mode"] = False

        st.divider()
        st.markdown("**Switch Session**")
        with st.container(height=300):
            if not sess_list:
                st.caption("No other sessions found.")
            for sid in sess_list:
                if sid == current_id: continue
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.write(sid)
                if c2.button("↩️", key=f"load_{sid}"):
                    st.session_state["session_id"] = sid
                    st.session_state["history"] = []
                    st.rerun()
                if c3.button("❌", key=f"del_{sid}"):
                    db_logic.delete_session(history_db, sid)
                    if st.session_state.get('session_id') == sid:
                        st.session_state['session_id'] = str(uuid4())
                        st.session_state['history'] = []
                    st.rerun()