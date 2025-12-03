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

# --- CSS FOR FIXED RIGHT SIDEBAR ---
# FIX: Scoped to 'section[data-testid="stMain"]' to prevent affecting the Left Sidebar
st.markdown(
    """
    <style>
    /* 1. Sidebar (Right Column) - Fixed to the right */
    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(2) {
        position: fixed; 
        right: 20px;
        top: 60px;
        width: 20%;
        height: 85vh;
        overflow-y: auto;
        padding-left: 10px;
        z-index: 1;
        border-left: 1px solid rgba(250, 250, 250, 0.2);
    }

    /* 2. Main Content (Left Column) - Needs a margin on the right */
    section[data-testid="stMain"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-of-type(1) {
        margin-right: 22%;
        padding-right: 20px;
    }
    
    /* Hide the default scrollbar on the right sidebar for a cleaner look */
    section[data-testid="stMain"] div[data-testid="stColumn"]:nth-of-type(2)::-webkit-scrollbar {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
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
    
    # 1. Render Left Sidebar & Get Configuration
    # (The CSS fix ensures columns inside here are NOT affected)
    config = sidebar.render_sidebar(history_db)

    # 2. Check Model Status
    if not st.session_state.get('model'):
        st.warning("Please configure a model in the sidebar to continue.")
        st.stop()

    # 3. Initialize Agent
    agent = entities.get_agent(
        model=st.session_state['model'],
        instructions=config.get("instructions"),
        kb_type=config.get("kb_type"),
        kb_config=config.get("kb_config"),
        session_id=st.session_state.get("session_id")
    )

    # 4. Load History (if empty/new session)
    if not st.session_state.history and st.session_state.get("session_id"):
        st.session_state.history = history.load_history_from_custom_db(
            history_db, 
            st.session_state.get("session_id")
        )

    # --- LAYOUT SETUP ---
    # This st.columns call is inside 'stMain', so our CSS will apply here.
    col_content, col_nav = st.columns([3, 1])

    # --- RIGHT COLUMN: Navigation ---
    with col_nav:
        st.subheader("List of Contents")
        if st.session_state.history:
            st.markdown("---")
            st.caption("Jump to message:")
            for idx, item in enumerate(st.session_state.history):
                # Truncate user text for the link label
                user_text = item.get("user", "")
                label = (user_text[:35] + '...') if len(user_text) > 35 else user_text
                if not label: 
                    label = f"Message {idx + 1}"
                
                # Create anchor link
                st.markdown(f"[{idx + 1}. {label}](#msg-{idx})")

    # --- LEFT COLUMN: Main Chat Interface ---
    with col_content:
        st.title("🧠 Agentic Chat")
        
        if st.session_state.get("session_id"):
            st.caption(f"Session ID: {st.session_state.get('session_id')}")
        
        # Display historical messages with Anchors
        history.render_history_ui()

        st.divider()

        # Handle Chat Run (Input + Streaming)
        chat.handle_chat_run(agent, config, history_db)

if __name__ == "__main__":
    main()