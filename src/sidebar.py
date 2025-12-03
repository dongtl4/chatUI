import streamlit as st
import os
from uuid import uuid4
from sqlalchemy import text
from agno.db.sqlite import SqliteDb
import entities
import history

def load_session_list(db: SqliteDb):
    sess_list = []
    try:
        with db.Session() as sess:
            stmt = text("SELECT DISTINCT session_id FROM chat_exchanges")
            rows = sess.execute(stmt).fetchall()
            for r in rows:
                if r[0]: sess_list.append(r[0])
    except Exception:
        pass
    return sess_list

def render_sidebar(history_db: SqliteDb):
    """Renders the sidebar and returns a configuration dictionary."""
    config = {
        "kb_type": "None",
        "kb_config": {},
        "instructions": "You are a helpful assistant.",
        "use_history": False,
        "history_length": 5,
        "use_full_history": True,
        "use_marked_context": False  # Default value
    }

    with st.sidebar:
        st.header("🔧 Configuration")

        # --- Model Configuration ---
        with st.expander("Model Configuration", expanded=False):
            model_provider = st.selectbox("Choose your model provider", ("DeepSeek", "OpenAI", "Ollama"))
            
            if 'initial' not in st.session_state:
                st.session_state['initial'] = True

            model_params = {}
            if model_provider == "OpenAI":
                model_params["api_key"] = st.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY"))
                model_params["id"] = st.text_input("Model ID", value="gpt-4o")
                model_params["name"] = st.text_input("Model name", value="OpenAI Agent")
            elif model_provider == "Ollama":
                model_params["id"] = st.text_input("Model ID", value="llama3.1:latest")
                model_params["host"] = st.text_input("Host", value="http://10.10.128.140:11434")
                model_params["name"] = st.text_input("Model name", value="Ollama Agent")
            elif model_provider == "DeepSeek":
                model_params["api_key"] = st.text_input("DeepSeek API Key", type="password", value=os.getenv("DEEPSEEK_API_KEY"))
                model_params["id"] = st.text_input("Model ID", value="deepseek-chat")
                model_params["name"] = st.text_input("Model name", value="Deepseek Agent")

            if st.session_state['initial'] and model_params.get("id"):
                 st.session_state['model'] = entities.create_model(model_provider, **model_params)
                 st.session_state['initial'] = False

            st.divider()
            config["instructions"] = st.text_area("Agent Instructions", value="You are a helpful assistant.", height=150)

            if st.button("Confirm Model", type="primary", disabled=bool(st.session_state.get('running', False))):
                st.session_state['model'] = entities.create_model(model_provider, **model_params)
                st.session_state.history = [] 
                st.success(f"{model_provider} model configured!")

        # --- Knowledge Base Configuration ---
        with st.expander("Knowledge Base Configuration", expanded=False):
            config["kb_type"] = st.selectbox("Knowledge Base Type", ("None", "PostgreSQL + PGVector"))
            
            if config["kb_type"] == "PostgreSQL + PGVector":
                config["kb_config"] = {
                    "host": st.text_input("PostgreSQL Host", value="localhost"),
                    "port": st.text_input("PostgreSQL Port", value="5432"),
                    "db": st.text_input("PostgreSQL Database", value="ai"),
                    "user": st.text_input("PostgreSQL User", value="postgres"),
                    "password": st.text_input("PostgreSQL Password", type="password", value="postgres"),
                    "table_name": st.text_input("Table Name", value="vectors"),
                    "knowledge_name": st.text_input("Knowledge name", value="PostgreSQL vector knowledge")
                }

        # --- Session History ---
        with st.expander("Session History", expanded=False):
            if "new_chat_mode" not in st.session_state:
                st.session_state["new_chat_mode"] = False

            if st.button("New Chat", key="new_chat_btn", disabled=bool(st.session_state.get('running', False))):
                st.session_state["new_chat_mode"] = True

            sess_list = load_session_list(history_db)

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
            st.markdown("**Existing sessions**")
            if not sess_list:
                st.info("No sessions found.")
            for sid in sess_list:
                c1, c2, c3 = st.columns([4, 1, 1])
                c1.write(sid)
                if c2.button("↩️", key=f"load_{sid}"):
                    st.session_state["session_id"] = sid
                    st.session_state["history"] = []
                    st.rerun()
                if c3.button("❌", key=f"del_{sid}"):
                    try:
                        with history_db.Session() as sess:
                            sess.execute(text("DELETE FROM chat_exchanges WHERE session_id = :sid"), {"sid": sid})
                            sess.commit()
                        if st.session_state.get('session_id') == sid:
                            st.session_state['session_id'] = str(uuid4())
                            st.session_state['history'] = []
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

        # --- Context Management ---
        with st.expander("Context Management", expanded=False):
            config["use_history"] = st.checkbox("Use chat history for context", value=False)
            if config["use_history"]:
                config["use_full_history"] = st.checkbox("Using full history", value=True)
                if not config["use_full_history"]:
                    config["history_length"] = st.number_input("Max history messages", min_value=1, max_value=20, value=5)
            
            st.divider()
            config["use_marked_context"] = st.checkbox("Include MARKED messages as important context", value=True)

        # --- Current Chat Navigation (Moved from main.py) ---
        with st.expander("Current Chat", expanded=True):
            if st.session_state.get("history"):
                st.caption("Jump / Mark Important:")
                
                # Iterate through history to display navigation and markers
                # We slice to exclude the very last active message if it's currently streaming/thinking
                display_history = st.session_state.history
                
                for idx, item in enumerate(display_history):
                    # We use cols to put checkbox and link side-by-side
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
                            
                            # Update state and DB if changed
                            if is_marked != item.get("marked", False):
                                history.toggle_exchange_marker(history_db, msg_id, is_marked)
                                item["marked"] = is_marked
                                st.rerun()

                    with c_link:
                        user_text = item.get("user", "")
                        label = (user_text[:20] + '...') if len(user_text) > 20 else user_text
                        if not label: label = f"Msg {idx + 1}"
                        st.markdown(f"[{idx + 1}. {label}](#msg-{idx})")
            else:
                st.caption("Start a conversation to see navigation.")

    return config