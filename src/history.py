import streamlit as st
from sqlalchemy import text
from typing import List, Dict, Any, Optional
import time

def save_message_to_db(db, session_id: str, role: str, content: str):
    """Manually saves a message to a custom table."""
    if not db or not session_id:
        return

    # Create table if not exists
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS custom_chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp INTEGER
    );
    """
    insert_sql = """
    INSERT INTO custom_chat_history (session_id, role, content, timestamp)
    VALUES (:session_id, :role, :content, :timestamp);
    """
    
    try:
        with db.Session() as sess:
            sess.execute(text(create_table_sql))
            sess.execute(text(insert_sql), {
                "session_id": session_id,
                "role": role,
                "content": content,
                "timestamp": int(time.time())
            })
            sess.commit()
    except Exception as e:
        print(f"Error saving to DB: {e}")

def load_history_from_custom_db(db, session_id: str) -> List[Dict[str, Any]]:
    """Loads history from the custom table and merges it."""
    merged = []
    if not session_id:
        return merged

    sql = """
    SELECT role, content 
    FROM custom_chat_history 
    WHERE session_id = :session_id 
    ORDER BY timestamp ASC
    """
    
    try:
        with db.Session() as sess:
            # Check if table exists first
            check_table = text("SELECT name FROM sqlite_master WHERE type='table' AND name='custom_chat_history'")
            if not sess.execute(check_table).fetchone():
                return []

            rows = sess.execute(text(sql), {"session_id": session_id}).fetchall()
            
            pending_user = None
            
            for row in rows:
                role = row.role
                content = row.content
                
                if role == "user":
                    if pending_user is not None:
                        merged.append({"user": pending_user, "assistant": ""})
                    pending_user = content
                elif role == "assistant":
                    if pending_user is None:
                        # Orphan assistant msg
                        if merged:
                            merged[-1]["assistant"] += content
                        else:
                            merged.append({"user": "", "assistant": content})
                    else:
                        merged.append({"user": pending_user, "assistant": content})
                        pending_user = None
            
            if pending_user:
                merged.append({"user": pending_user, "assistant": ""})
                
    except Exception as e:
        print(f"DB Load Error: {e}")
        
    return merged

def render_history_ui():
    """Renders the chat history from session state."""
    # If running, ignore the last entry (it's being built)
    history_to_show = st.session_state.history[:-1] if st.session_state.get('running', None) is not None else st.session_state.history

    for entry in history_to_show:
        with st.chat_message("user"):
            st.markdown(entry.get("user", "") or "_(no user message)_")
        with st.chat_message("assistant"):
            st.markdown(entry.get("assistant", "") or "_(no assistant message)_")