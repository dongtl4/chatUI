import streamlit as st
from sqlalchemy import text
from typing import List, Dict, Any
import time

def save_exchange_to_db(db, session_id: str, user_content: str, assistant_content: str):
    """
    Saves a complete conversation turn (User Input + Assistant Response) as a single atomic unit.
    """
    if not db or not session_id:
        return

    # New table schema: stores both parts of the conversation in one row
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_exchanges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        user_content TEXT,
        assistant_content TEXT,
        timestamp INTEGER
    );
    """
    
    insert_sql = """
    INSERT INTO chat_exchanges (session_id, user_content, assistant_content, timestamp)
    VALUES (:session_id, :user_content, :assistant_content, :timestamp);
    """
    
    try:
        with db.Session() as sess:
            sess.execute(text(create_table_sql))
            sess.execute(text(insert_sql), {
                "session_id": session_id,
                "user_content": user_content,
                "assistant_content": assistant_content,
                "timestamp": int(time.time())
            })
            sess.commit()
    except Exception as e:
        print(f"Error saving exchange to DB: {e}")

def load_history_from_custom_db(db, session_id: str) -> List[Dict[str, Any]]:
    """
    Loads conversation pairs directly. No merging logic required.
    """
    history = []
    if not session_id:
        return history

    sql = """
    SELECT user_content, assistant_content
    FROM chat_exchanges 
    WHERE session_id = :session_id 
    ORDER BY timestamp ASC
    """
    
    try:
        with db.Session() as sess:
            # Check if table exists first
            check_table = text("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_exchanges'")
            if not sess.execute(check_table).fetchone():
                return []

            rows = sess.execute(text(sql), {"session_id": session_id}).fetchall()
            
            for row in rows:
                history.append({
                    "user": row.user_content,
                    "assistant": row.assistant_content
                })
                
    except Exception as e:
        print(f"DB Load Error: {e}")
        
    return history

def render_history_ui():
    """Renders the chat history from session state."""
    # If running, ignore the last entry (it's being built)
    history_to_show = st.session_state.history[:-1] if st.session_state.get('running', None) is not None else st.session_state.history

    for entry in history_to_show:
        with st.chat_message("user"):
            st.markdown(entry.get("user", "") or "_(no user message)_")
        with st.chat_message("assistant"):
            st.markdown(entry.get("assistant", "") or "_(no assistant message)_")