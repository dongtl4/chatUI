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
    
    # 1. Render Sidebar & Get Configuration
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
    col_content, col_nav = st.columns([4, 1])

    # --- RIGHT COLUMN: Navigation & Marking ---
    with col_nav:
        st.subheader("Start of Chat")
        if st.session_state.history:
            st.markdown("---")
            st.caption("Jump / Mark Important:")
            
            for idx, item in enumerate(st.session_state.history):
                # We use cols to put checkbox and link side-by-side
                c_mark, c_link = st.columns([0.2, 0.8])
                
                with c_mark:
                    # Checkbox to toggle 'marked' status
                    # We key it by the message ID to ensure uniqueness
                    # The message must have been saved to DB to have an ID. New streaming messages might not have an ID yet.
                    msg_id = item.get("id")
                    if msg_id:
                        is_marked = st.checkbox(
                            "Mark", 
                            value=item.get("marked", False), 
                            key=f"mark_chk_{msg_id}",
                            label_visibility="collapsed"
                        )
                        
                        # If state changed in UI, update DB and local state
                        if is_marked != item.get("marked", False):
                            history.toggle_exchange_marker(history_db, msg_id, is_marked)
                            item["marked"] = is_marked
                            st.rerun()

                with c_link:
                    user_text = item.get("user", "")
                    label = (user_text[:25] + '...') if len(user_text) > 25 else user_text
                    if not label: label = f"Msg {idx + 1}"
                    st.markdown(f"[{idx + 1}. {label}](#msg-{idx})")

    # --- LEFT COLUMN: Main Chat Interface ---
    with col_content:
        st.title("🧠 Agentic Chat")
        
        if st.session_state.get("session_id"):
            st.caption(f"Session ID: {st.session_state.get('session_id')}")
        
        # Display historical messages
        history.render_history_ui()

        st.divider()

        # Handle Chat Run
        chat.handle_chat_run(agent, config, history_db)

if __name__ == "__main__":
    main()