import time
import json
from sqlalchemy import text
from agno.db.sqlite import SqliteDb

def get_db(db_path: str = "tmp/custom_chat.db") -> SqliteDb:
    """Returns the database instance."""
    return SqliteDb(db_file=db_path)

def load_session_list(db: SqliteDb):
    """Retrieves a list of available session IDs."""
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

def save_exchange_to_db(db, session_id: str, user_content: str, assistant_content: str):
    """Saves a complete conversation turn."""
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

def load_history_from_db(db, session_id: str):
    """Loads conversation pairs."""
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

def delete_session(db, session_id: str):
    """Deletes a session (chat history and associated documents) from the DB."""
    try:
        with db.Session() as sess:
            # 1. Delete the chat history
            sess.execute(text("DELETE FROM chat_exchanges WHERE session_id = :sid"), {"sid": session_id}) 
            # 2. Delete the associated marked documents configuration
            sess.execute(text("DELETE FROM session_documents WHERE session_id = :sid"), {"sid": session_id})            
            sess.commit()
    except Exception as e:
        print(f"Error deleting session: {e}")

def delete_marked_exchanges(db, session_id: str):
    """Deletes all marked exchanges for a session."""
    try:
        with db.Session() as sess:
            sess.execute(text("DELETE FROM chat_exchanges WHERE session_id = :sid AND is_marked = 1"), {"sid": session_id})
            sess.commit()
    except Exception as e:
        print(f"Error deleting marked exchanges: {e}")

# --- DOCUMENT MANAGEMENT ---

def ensure_session_docs_table(sess):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS session_documents (
        session_id TEXT,
        metaid TEXT,
        PRIMARY KEY (session_id, metaid)
    );
    """
    sess.execute(text(create_table_sql))

def save_session_documents(db, session_id: str, metaids: list):
    """Saves the list of marked document metaids for a session (Full Refresh)."""
    if not db or not session_id:
        return

    try:
        with db.Session() as sess:
            ensure_session_docs_table(sess)
            
            # Clear existing selection for this session
            sess.execute(text("DELETE FROM session_documents WHERE session_id = :sid"), {"sid": session_id})
            
            # Insert new selection
            if metaids:
                insert_sql = "INSERT INTO session_documents (session_id, metaid) VALUES (:sid, :mid)"
                for mid in metaids:
                    sess.execute(text(insert_sql), {"sid": session_id, "mid": mid})
            
            sess.commit()
    except Exception as e:
        print(f"Error saving session documents: {e}")

def get_session_documents(db, session_id: str) -> list:
    """Retrieves the list of metaids associated with a session."""
    if not db or not session_id:
        return []

    try:
        with db.Session() as sess:
            ensure_session_docs_table(sess)
            sql = text("SELECT metaid FROM session_documents WHERE session_id = :sid")
            rows = sess.execute(sql, {"sid": session_id}).fetchall()
            return [row[0] for row in rows]
    except Exception as e:
        print(f"Error loading session documents: {e}")
        return []

def remove_document_from_usages(db, metaid: str):
    """Removes a document from ALL sessions (used when file is deleted)."""
    if not db or not metaid:
        return
        
    try:
        with db.Session() as sess:
            ensure_session_docs_table(sess)
            sess.execute(text("DELETE FROM session_documents WHERE metaid = :mid"), {"mid": metaid})
            sess.commit()
    except Exception as e:
        print(f"Error removing document usages: {e}")

# --- AGENT CONFIGURATION MANAGEMENT ---

def ensure_agent_configs_table(sess):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS agent_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        config_json TEXT,
        timestamp INTEGER
    );
    """
    sess.execute(text(create_table_sql))

def save_agent_config(db, name: str, config_data: dict):
    """Saves the current agent configuration (params + prompt)."""
    if not db or not name:
        return False
    
    try:
        with db.Session() as sess:
            ensure_agent_configs_table(sess)
            # Check if name exists to update or insert new (optional, here we just insert new for history)
            # For simplicity, let's just insert a new record. 
            # If you want unique names, you'd check first.
            
            insert_sql = """
            INSERT INTO agent_configs (name, config_json, timestamp)
            VALUES (:name, :config_json, :timestamp)
            """
            sess.execute(text(insert_sql), {
                "name": name,
                "config_json": json.dumps(config_data),
                "timestamp": int(time.time())
            })
            sess.commit()
        return True
    except Exception as e:
        print(f"Error saving agent config: {e}")
        return False

def list_agent_configs(db):
    """Returns a list of saved agent configurations."""
    configs = []
    if not db:
        return configs
        
    try:
        with db.Session() as sess:
            ensure_agent_configs_table(sess)
            sql = text("SELECT id, name, config_json, timestamp FROM agent_configs ORDER BY timestamp DESC")
            rows = sess.execute(sql).fetchall()
            for row in rows:
                configs.append({
                    "id": row[0],
                    "name": row[1],
                    "config": json.loads(row[2]),
                    "timestamp": row[3]
                })
    except Exception as e:
        print(f"Error listing agent configs: {e}")
    return configs

def delete_agent_config(db, config_id: int):
    """Deletes a specific agent configuration."""
    try:
        with db.Session() as sess:
            ensure_agent_configs_table(sess)
            sess.execute(text("DELETE FROM agent_configs WHERE id = :id"), {"id": config_id})
            sess.commit()
    except Exception as e:
        print(f"Error deleting agent config: {e}")