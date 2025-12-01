import streamlit as st
from dotenv import load_dotenv
from agno.db.sqlite import SqliteDb

# Import modules
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

# Initialize Session State
if "history" not in st.session_state:
    st.session_state.history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = None
if "model" not in st.session_state:
    st.session_state.model = None
if "running" not in st.session_state:
    st.session_state.running = None
if "current_chat" not in st.session_state:
    st.session_state.current_chat = []

# Global DB connection for history
DB_FILE = "tmp/chat.db"
history_db = SqliteDb(db_file=DB_FILE)

def main():
    st.title("🧠 Agentic RAG Chat")

    # 1. Render Sidebar & Get Configuration
    config = sidebar.render_sidebar(history_db)

    # 2. Check Model Status
    if not st.session_state.get('model'):
        st.warning("Please configure a model in the sidebar to continue.")
        st.stop()

    # 3. Initialize Agent & Knowledge
    # We pass the model object from session_state (created in sidebar/entities)
    agent = entities.get_agent(
        model=st.session_state['model'],
        instructions=config.get("instructions"),
        kb_type=config.get("kb_type"),
        kb_config=config.get("kb_config"),
        history_db=history_db,
        session_id=st.session_state.get("session_id")
    )

    # 4. Load & Render History
    # Load from DB if history is empty (first load)
    if not st.session_state.history and st.session_state.get("session_id"):
        st.session_state.history = history.load_history_from_db(agent)
    
    st.subheader(f"Current session: **{st.session_state.get('session_id')}**")
    
    # Display historical messages
    history.render_history_ui()

    st.divider()

    # 5. Handle Chat Run
    chat.handle_chat_run(agent, config)

if __name__ == "__main__":
    main()