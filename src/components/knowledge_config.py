import streamlit as st

import os

def get_env_defaults():
    """Reads environment variables for DB config."""
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": os.getenv("PG_PORT", "5432"),
        "db": os.getenv("PG_DB", "testing"),
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.getenv("PG_PASSWORD", "123456"),
        "table_name": "vectors",
        "max_results": 10,
        "knowledge_name": "Default Knowledge Base"
    }

def auto_initialize():
    """
    Populates session state with default KB config if not present.
    If Env vars are robust, it sets the KB as active immediately.
    """
    if "kb_confirmed_config" not in st.session_state:
        defaults = get_env_defaults()
        st.session_state['kb_confirmed_config'] = defaults
        # Assume if we have defaults, we want to try using them
        st.session_state['kb_active_type'] = "PostgreSQL + PGVector"

def render():
    st.header("🔌 Knowledge Base Connection")
    
    # Load whatever is in session state (set by auto_initialize)
    current_config = st.session_state.get('kb_confirmed_config', get_env_defaults())
    
    selected_kb_type = st.selectbox(
        "Knowledge Base Type", 
        ("PostgreSQL + PGVector", "None"),
        index=0 if st.session_state.get('kb_active_type') == "PostgreSQL + PGVector" else 1
    )
    
    if selected_kb_type == "PostgreSQL + PGVector":
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Database")
            kb_host = st.text_input("PostgreSQL Host", value=current_config.get("host"))
            kb_port = st.text_input("PostgreSQL Port", value=current_config.get("port"))
            kb_db = st.text_input("PostgreSQL Database", value=current_config.get("db"))
        
        with col2:
            st.subheader("Auth & Table")
            kb_user = st.text_input("PostgreSQL User", value=current_config.get("user"))
            kb_password = st.text_input("PostgreSQL Password", type="password", value=current_config.get("password"))
            kb_table = st.text_input("Table Name", value=current_config.get("table_name"))
        
        kb_name = st.text_input("Knowledge name", value=current_config.get("knowledge_name"))
        kb_max_results = st.number_input("Max Results", value=current_config.get("max_results"))

        if st.button("Save & Reconnect", type="primary"):
            st.session_state['kb_confirmed_config'] = {
                "host": kb_host, "port": kb_port, "db": kb_db, 
                "user": kb_user, "password": kb_password, 
                "table_name": kb_table, "max_results": kb_max_results,
                "knowledge_name": kb_name
            }
            st.session_state['kb_active_type'] = selected_kb_type
            st.success("Configuration updated!")
            
    else:
        if st.button("Disable Knowledge Base"):
            st.session_state['kb_active_type'] = "None"
            st.rerun()