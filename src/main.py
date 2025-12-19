import streamlit as st
from dotenv import load_dotenv

# Logic imports
from src.core import db as db_logic
from src.core import agent as agent_logic

# Component imports
from src.components import sidebar, chat, agent_config, context_config, knowledge_config, knowledge_ui

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(page_title="Agentic Chat", page_icon="🧠", layout="wide")

# Initialize DB
DB_FILE = "tmp/custom_chat.db"
history_db = db_logic.get_db(DB_FILE)

def main():
    # 1. Component Auto-Initialization
    # We let each component decide its default state based on env vars
    context_config.auto_initialize()
    knowledge_config.auto_initialize()
    agent_config.auto_initialize()

    # 2. Global State Safety Checks
    if "current_view" not in st.session_state:
        st.session_state["current_view"] = "chat_interface"
    if "running" not in st.session_state:
        st.session_state["running"] = None
    if "current_chat" not in st.session_state:
        st.session_state["current_chat"] = []

    # 3. Load History (if session exists)
    if st.session_state.get("session_id") and not st.session_state.history:
        st.session_state.history = db_logic.load_history_from_db(
            history_db, st.session_state.get("session_id")
        )

    # 4. Construct Agent Wrapper
    # Combines the Model (from agent_config) with KB Config (from knowledge_config)
    agent = None
    if st.session_state.get('model'):
        agent = agent_logic.get_agent(
            model=st.session_state['model'],
            instructions=st.session_state.get("agent_instructions", ""),
            kb_type=st.session_state.get('kb_active_type', 'None'),
            kb_config=st.session_state.get('kb_confirmed_config', {}),
            session_id=st.session_state.get("session_id")
        )

    # 5. Render Sidebar
    sidebar.render_sidebar(history_db)

    # 6. Route Main View
    view = st.session_state.get("current_view", "chat_interface")
    

    if view == "chat_interface":
        chat.render(agent, history_db)
    elif view == "context_config":
        context_config.render(history_db)
    elif view == "agent_config":
        agent_config.render()
    elif view == "knowledge_config":
        knowledge_config.render()
    elif view == "knowledge_ui":
        knowledge_ui.render(history_db)
    else:
        st.error(f"Unknown view: {view}")

if __name__ == "__main__":
    main()