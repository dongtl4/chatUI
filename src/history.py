import streamlit as st
from sqlalchemy import text
from typing import List, Dict, Any
import time

def save_exchange_to_db(db, session_id: str, user_content: str, assistant_content: str):
    """
    Saves a complete conversation turn.
    """
    if not db or not session_id:
        return

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS chat_exchanges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        user_content TEXT,
        assistant_content TEXT,
        timestamp INTEGER,
        is_marked BOOLEAN DEFAULT 0
    );
    """
    
    insert_sql = """
    INSERT INTO chat_exchanges (session_id, user_content, assistant_content, timestamp, is_marked)
    VALUES (:session_id, :user_content, :assistant_content, :timestamp, 0);
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

def toggle_exchange_marker(db, exchange_id: int, new_value: bool):
    """Updates the marked status of a specific exchange."""
    sql = "UPDATE chat_exchanges SET is_marked = :val WHERE id = :id"
    try:
        with db.Session() as sess:
            sess.execute(text(sql), {"val": 1 if new_value else 0, "id": exchange_id})
            sess.commit()
    except Exception as e:
        print(f"Error toggling marker: {e}")

def load_history_from_custom_db(db, session_id: str) -> List[Dict[str, Any]]:
    """
    Loads conversation pairs, including their ID and marked status.
    """
    history = []
    if not session_id:
        return history

    sql = """
    SELECT id, user_content, assistant_content, is_marked
    FROM chat_exchanges 
    WHERE session_id = :session_id 
    ORDER BY timestamp ASC
    """
    
    try:
        with db.Session() as sess:
            check_table = text("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_exchanges'")
            if not sess.execute(check_table).fetchone():
                return []

            rows = sess.execute(text(sql), {"session_id": session_id}).fetchall()
            
            for row in rows:
                history.append({
                    "id": row.id,
                    "user": row.user_content,
                    "assistant": row.assistant_content,
                    "marked": bool(row.is_marked)
                })
                
    except Exception as e:
        print(f"DB Load Error: {e}")
        
    return history

def render_history_ui():
    """Renders the chat history from session state."""
    # If running, ignore the last entry (it's being built)
    history_to_show = st.session_state.history[:-1] if st.session_state.get('running', None) is not None else st.session_state.history

    for idx, entry in enumerate(history_to_show):
        st.markdown(f"<div id='msg-{idx}'></div>", unsafe_allow_html=True)
        
        # Visual indicator if marked
        if entry.get("marked"):
            st.caption(f"📌 Marked Context (ID: {entry.get('id')})")

        with st.chat_message("user"):
            st.markdown(entry.get("user", "") or "_(no user message)_")
        with st.chat_message("assistant"):
            st.markdown(entry.get("assistant", "") or "_(no assistant message)_")