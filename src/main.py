import streamlit as st
from dotenv import load_dotenv
from agno.db.sqlite import SqliteDb

# Import local modules
import sidebar
import entities
import history
import chat

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Agentic Chat",
    page_icon="🧠",
    layout="wide"
)

# Global DB connection (initialized once)
DB_FILE = "tmp/custom_chat.db"
history_db = SqliteDb(db_file=DB_FILE)

def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "history": [],
        "session_id": None,
        "model": None,
        "running": None,
        "current_chat": []
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def main():
    init_session_state()
    st.title("🧠 Agentic Chat")

    # 1. Render Sidebar & Get Configuration
    config = sidebar.render_sidebar(history_db)

    # 2. Check Model Status
    if not st.session_state.get('model'):
        st.warning("Please configure a model in the sidebar to continue.")
        st.stop()

    # 3. Initialize Agent
    # We remove the 'db' param here to handle history manually
    agent = entities.get_agent(
        model=st.session_state['model'],
        instructions=config.get("instructions"),
        kb_type=config.get("kb_type"),
        kb_config=config.get("kb_config"),
        session_id=st.session_state.get("session_id")
    )

    # 4. Load & Render History
    # Load from DB if history is empty (first load of a session)
    if not st.session_state.history and st.session_state.get("session_id"):
        st.session_state.history = history.load_history_from_custom_db(
            history_db, 
            st.session_state.get("session_id")
        )
    
    if st.session_state.get("session_id"):
        st.subheader(f"Current session: **{st.session_state.get('session_id')}**")
    
    # Display historical messages
    history.render_history_ui()

    st.divider()

    # 5. Handle Chat Run
    # We pass history_db so chat.py can save messages manually
    chat.handle_chat_run(agent, config, history_db)

if __name__ == "__main__":
    main()